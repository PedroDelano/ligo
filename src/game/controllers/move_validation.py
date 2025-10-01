from typing import Optional

import pydantic

from ..models import GAME_STATUS, Board, Game, LastMoveCache
from ..responses import ErrorCode
from ..rules import models


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
