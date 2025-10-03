import random
import time
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.conf import settings
from typing import Optional

from bot.models import BotGame
from game.models import Board, LastMoveCache, Move
from game.rules import capture
from game.rules import models as rule_models
from bot.engines.cores.pachi import PachiBot
from bot.engines.cores.random import RandomBot

logger = logging.getLogger()


class BotService:
    """Service for bot move logic"""

    # Bot engine factory
    ENGINE_MAP = {
        "random": RandomBot,
        "simple": PachiBot,
        "intermediate": PachiBot,
        "advanced": PachiBot,
    }

    @classmethod
    def _get_engine(cls, difficulty: str, board_size: int):
        """Get the appropriate bot engine for difficulty level"""
        engine_class = cls.ENGINE_MAP.get(difficulty, RandomBot)
        logging.info(f"Starting engine: {difficulty}")

        # Pass pachi path if needed (configure in settings)
        if engine_class == PachiBot:
            pool_size = getattr(settings, "PACHI_POOL_SIZE", 1)
            return engine_class(
                board_size=board_size, difficulty=difficulty, pool_size=pool_size
            )

        return engine_class(board_size, difficulty)

    @classmethod
    def _prepare_game_state(cls, board: Board) -> dict:
        """Prepare game state for bot engine"""
        moves = list(
            Move.objects.filter(board=board)
            .order_by("move_number")
            .values("x", "y", "color", "move_number")
        )

        return {
            "board_size": board.size,
            "moves": moves,
            "captured_stones": {
                # TODO: Add a count for captured for black and white
                # - board.captured_black
                # - board.captured_white
                "black": 0,
                "white": 0,
            },
        }

    @staticmethod
    def is_bot_turn(board_id: int) -> bool:
        """Check if it's the bot's turn to move"""
        try:
            board = Board.objects.get(id=board_id)
            bot_game = BotGame.objects.filter(game=board.game).first()

            if not bot_game:
                return False

            # Get the highest move number to determine whose turn it is
            # Use move_number, not count of alive moves (captures change alive count!)
            last_move = (
                Move.objects.filter(board=board).order_by("-move_number").first()
            )

            if last_move is None:
                # No moves yet, black goes first
                move_number = 0
            else:
                move_number = last_move.move_number

            # Black goes first (move_number is even), white goes second (move_number is odd)
            if move_number % 2 == 0:
                # Black's turn
                return bot_game.bot_color == "B"
            else:
                # White's turn
                return bot_game.bot_color == "W"

        except (Board.DoesNotExist, BotGame.DoesNotExist):
            return False

    @staticmethod
    def _get_valid_moves(board, color):
        """Get list of valid moves for the given color"""
        # Get current board state
        moves = list(
            Move.objects.filter(board=board, alive=True)
            .order_by("move_number")
            .values("x", "y", "color", "move_number")
        )

        valid_positions = []

        for i in range(board.size):
            for j in range(board.size):
                # Check if position is empty
                occupied = any(m["x"] == i and m["y"] == j for m in moves)
                if occupied:
                    continue

                # Test if move is valid (not suicide)
                test_moves = moves + [
                    {"x": i, "y": j, "color": color, "move_number": len(moves)}
                ]
                game_model = rule_models.Game(
                    board=rule_models.Board(size=board.size),
                    moves=[rule_models.Move(**m) for m in test_moves],
                )

                # IMPORTANT: Pass OPPOSITE color, same as in place_stone view
                # This checks what gets captured after our move
                _, captured = capture.Capture.remove_captured_stones(
                    game_model, last_played_color="W" if color == "B" else "B"
                )

                # Check if this move would be suicide
                test_move = rule_models.Move(
                    x=i, y=j, color=color, move_number=len(moves)
                )
                if test_move not in captured:
                    valid_positions.append((i, j))

        return valid_positions

    @staticmethod
    def _make_pass(board, color, move_number):
        """Make a pass move"""

        # Check if the last move was also a pass - if so, game ends
        last = (
            LastMoveCache.objects.select_related("move")
            .filter(board=board)
            .values("move__color", "move__move_number", "move__x", "move__y")
            .first()
        )

        if last is not None and last.get("move__x") == -1 and last.get("move__y") == -1:
            # Both players passed - end the game
            # Import here to avoid circular dependency
            from game.controllers.finish_game import FinishGame

            # Create the bot's pass move first
            m = Move.objects.create(
                board=board,
                move_number=move_number,
                x=-1,
                y=-1,
                color=color,
                alive=True,
            )

            LastMoveCache.objects.update_or_create(
                board=board,
                defaults={"move_id": m.id},
            )

            # Now finish the game
            score_data, territory_data = FinishGame.finish_game(board.id)

            # Notify game ended
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"board_{board.id}",
                {"type": "board.update", "payload": {"type": "game_ended"}},
            )
            return

        # Normal pass - not ending the game
        m = Move.objects.create(
            board=board, move_number=move_number, x=-1, y=-1, color=color, alive=True
        )

        LastMoveCache.objects.update_or_create(
            board=board,
            defaults={"move_id": m.id},
        )

        # Notify via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"board_{board.id}",
            {"type": "board.update", "payload": {"type": "pass"}},
        )

    @classmethod
    @transaction.atomic
    def commit_move(
        cls, x: int, y: int, move_count: int, board: Board, bot_game: BotGame
    ) -> None:
        # Handle captures after bot's move - following the same pattern as board_state
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert isinstance(move_count, int)

        # Create move
        move = Move.objects.create(
            board=board,
            x=x,
            y=y,
            color=bot_game.bot_color,
            move_number=move_count + 1,
        )

        moves = list(
            Move.objects.filter(board=board, alive=True)
            .order_by("move_number")
            .values("x", "y", "color", "move_number")
        )

        game_model = rule_models.Game(
            board=rule_models.Board(size=board.size),
            moves=[rule_models.Move(**mv) for mv in moves],
        )

        # Pass the bot's color as last_played_color (the color that just moved)
        _, captured_stones = capture.Capture.remove_captured_stones(
            game_model, last_played_color=bot_game.bot_color
        )

        # Mark captured stones in the database
        if len(captured_stones) > 0:
            capture.Capture.mark_captured(board, captured_stones)

        if len(moves) > 0:
            LastMoveCache.objects.update_or_create(
                board=board,
                defaults={"move_id": move.id},
            )

        # Notify via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"board_{board.id}",
            {"type": "board.update", "payload": {"type": "move"}},
        )

    @classmethod
    @transaction.atomic
    def make_bot_move(cls, board_id: int) -> Optional[dict]:
        """Make a bot move on the given board"""

        # Ensures db commits
        # TODO: There must be a better way to do this
        time.sleep(0.3)

        try:
            board = Board.objects.select_for_update().get(id=board_id)
            bot_game = BotGame.objects.select_related("bot_player").get(game=board.game)

            # Check if it's bot's turn
            move_count = Move.objects.filter(board=board).count()
            is_black_turn = move_count % 2 == 0
            bot_is_black = bot_game.bot_color == "B"

            if is_black_turn != bot_is_black:
                logger.warning(f"Not bot's turn on board {board_id}")
                return None

            # Get bot engine
            engine = cls._get_engine(bot_game.bot_player.difficulty, board.size)

            # Get game state
            game_state = cls._prepare_game_state(board)

            # Select move
            move_coords = engine.select_move(game_state)

            # Check if bot should pass
            if move_coords is None or engine.should_pass(game_state):
                move_coords = (-1, -1)

            # Create move
            x, y = move_coords
            cls.commit_move(
                x=x, y=y, move_count=move_count, board=board, bot_game=bot_game
            )
            logger.info(
                f"Bot made move on board {board_id}: {bot_game.bot_color} at ({x}, {y})"
            )

            return {"x": x, "y": y, "color": bot_game.bot_color}

        except Board.DoesNotExist:
            logger.error(f"Board {board_id} not found")
            return None
        except BotGame.DoesNotExist:
            logger.error(f"BotGame not found for board {board_id}")
            return None
        except Exception as e:
            logger.error(f"Error making bot move: {e}", exc_info=True)
            return None
