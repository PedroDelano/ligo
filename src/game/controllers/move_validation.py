from typing import List, Optional

import pydantic

from ..models import GAME_STATUS, Board, Game, LastMoveCache
from ..responses import ErrorCode
from ..rules import capture, groups, models


class MoveValidationOutput(pydantic.BaseModel):
    is_valid: bool
    error_code: Optional[ErrorCode] = None
    message: Optional[str] = None
    current_color: Optional[models.StoneColor] = None
    current_move_number: Optional[int] = None


class MoveValidation:
    @staticmethod
    def is_valid_move(request, board_id: int) -> MoveValidationOutput:
        assert hasattr(request, "user")
        assert isinstance(board_id, int)

        board = Board.objects.select_for_update().get(id=board_id)
        if not board:
            return MoveValidationOutput(
                is_valid=False, error_code=ErrorCode.BOARD_NOT_FOUND
            )
        game = Game.objects.select_for_update().get(id=board.game_id)
        if not game:
            return MoveValidationOutput(
                is_valid=False, error_code=ErrorCode.GAME_NOT_FOUND
            )
        if game.status != GAME_STATUS.ONGOING.value:
            return MoveValidationOutput(is_valid=False, error_code=ErrorCode.GAME_ENDED)

        if request.user not in [game.user_white, game.user_black]:
            return MoveValidationOutput(is_valid=False, error_code=ErrorCode.FORBIDDEN)

        last = (
            LastMoveCache.objects.select_related("move")
            .filter(board=board)
            .values("move__color", "move__move_number", "move__x", "move__y")
            .first()
        )

        color = (
            models.StoneColor.BLACK
            if request.user == game.user_black
            else models.StoneColor.WHITE
        )

        if last is not None and last.get("move__color") == color.value:
            return MoveValidationOutput(
                is_valid=False, error_code=ErrorCode.NOT_YOUR_TURN
            )

        return MoveValidationOutput(
            is_valid=True,
            current_color=color,
            current_move_number=last.get("move__move_number") if last else 0,
        )

    @classmethod
    def is_suicide_move(cls, board: Board, moves: List[dict], color: models.StoneColor):
        assert isinstance(moves, list)
        assert isinstance(color, models.StoneColor)
        for x in moves:
            # Assert dict entry
            models.Move(**x)

        # Create the game model with the new move
        game_model = models.Game(
            board=models.Board(size=board.size),
            moves=[models.Move(**move) for move in moves],
        )
        last_move = models.Move(**moves[-1])

        # Get the GROUP that the last move belongs to, not just the single stone
        group = groups.Groups.get_group(game_model, last_move)
        group_liberty = group.liberties

        if group_liberty == 0:
            # Check if placing this stone would capture any enemy stones
            # IMPORTANT: Use invert_color=True to check ENEMY captures, not our own color
            game_after_capture, captured_enemy_stones = (
                capture.Capture.remove_captured_stones(
                    game_model,
                    last_played_color=color.value,
                    invert_color=True,
                    debug=False,
                )
            )

            # If no enemy stones were captured and we have 0 liberties, it's suicide
            if len(captured_enemy_stones) == 0:
                return MoveValidationOutput(
                    is_valid=False, error_code=ErrorCode.INVALID_MOVE
                )

            # If enemy stones WERE captured, check if our group now has liberties
            # after those captures are removed from the board
            else:
                # Find our stone in the game state after captures
                our_stone_in_new_state = next(
                    (
                        m
                        for m in game_after_capture.moves
                        if m.x == last_move.x and m.y == last_move.y
                    ),
                    None,
                )

                if our_stone_in_new_state:
                    # Get the group and recalculate liberties after enemy captures
                    group_after_capture = groups.Groups.get_group(
                        game_after_capture, our_stone_in_new_state
                    )
                    group_liberty_after_capture = group_after_capture.liberties

                    # If still 0 liberties even after capturing enemy stones, it's suicide
                    if group_liberty_after_capture == 0:
                        return MoveValidationOutput(
                            is_valid=False, error_code=ErrorCode.INVALID_MOVE
                        )

        return MoveValidationOutput(is_valid=True)
