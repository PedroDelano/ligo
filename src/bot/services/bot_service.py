from game.models import Board, Move, LastMoveCache
from bot.models import BotGame, BotPlayer
from django.db import transaction
from game.controllers.move_validation import MoveValidation
from game.rules import capture, models as rule_models
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import random
import time


class BotService:
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
    @transaction.atomic
    def make_bot_move(board_id: int):
        """Make a bot move on the board"""

        # Small delay to ensure previous transaction has committed
        time.sleep(0.1)

        board = Board.objects.select_for_update().get(id=board_id)
        bot_game = BotGame.objects.get(game=board.game)

        # Determine current color using move_number, not alive count
        last_move = Move.objects.filter(board=board).order_by("-move_number").first()

        if last_move is None:
            current_move_number = 0
            current_color = "B"
        else:
            current_move_number = last_move.move_number
            current_color = "B" if current_move_number % 2 == 0 else "W"

        # Verify it's actually the bot's turn
        if current_color != bot_game.bot_color:
            return

        # Get valid moves
        valid_moves = BotService._get_valid_moves(board, current_color)

        if not valid_moves:
            # No valid moves, pass
            BotService._make_pass(board, current_color, current_move_number + 1)
            return

        # Simple bot logic - choose random valid move
        move = random.choice(valid_moves)

        # Create the move
        m = Move.objects.create(
            board=board,
            move_number=current_move_number + 1,
            x=move[0],
            y=move[1],
            color=current_color,
            alive=True,
        )

        LastMoveCache.objects.update_or_create(
            board=board,
            defaults={"move_id": m.id},
        )

        # Handle captures after bot's move - following the same pattern as board_state
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
        current_game_state, captured_stones = capture.Capture.remove_captured_stones(
            game_model, last_played_color=current_color
        )

        # Mark captured stones in the database
        if len(captured_stones) > 0:
            capture.Capture.mark_captured(board, captured_stones)

        # Notify via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"board_{board.id}",
            {"type": "board.update", "payload": {"type": "move"}},
        )

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
