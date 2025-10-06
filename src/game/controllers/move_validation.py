from typing import Optional, List

import pydantic

from ..models import GAME_STATUS, Board, Game, LastMoveCache
from ..responses import ErrorCode
from ..rules import models, groups, capture


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

        # we only need to worry about suicide if there's 0 liberties
        game_model = models.Game(
            board=models.Board(size=board.size),
            moves=[models.Move(**move) for move in moves],
        )
        last_move = models.Move(**moves[-1])
        stone_liberty, _ = groups.Groups.count_liberties_for_group(
            [last_move], game_model
        )

        if stone_liberty == 0:
            # Check if placing this stone would capture any enemy stones
            # IMPORTANT: Use invert_color=True to check ENEMY captures, not our own color
            game_after_capture, captured_enemy_stones = (
                capture.Capture.remove_captured_stones(
                    game_model,
                    last_played_color=color.value,
                    invert_color=True,
                    debug=True,
                )
            )

            # If no enemy stones were captured and we have 0 liberties, it's suicide
            if len(captured_enemy_stones) == 0:
                return MoveValidationOutput(
                    is_valid=False, error_code=ErrorCode.INVALID_MOVE
                )

            # If enemy stones WERE captured, check if our stone now has liberties
            # after those captures are removed from the board
            else:
                # Find our stone in the game state after captures
                our_stone_in_new_state = next(
                    (m for m in game_after_capture.moves if m.x == x and m.y == y), None
                )

                if our_stone_in_new_state:
                    # Recalculate liberties for our stone after enemy captures
                    stone_liberty_after_capture, _ = (
                        groups.Groups.count_liberties_for_group(
                            [our_stone_in_new_state], game_after_capture
                        )
                    )

                    # If still 0 liberties even after capturing enemy stones, it's suicide
                    if stone_liberty_after_capture == 0:
                        return MoveValidationOutput(
                            is_valid=False, error_code=ErrorCode.INVALID_MOVE
                        )

        return MoveValidationOutput(is_valid=True)
