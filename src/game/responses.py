from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel


class ErrorCode(StrEnum):
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    NOT_YOUR_TURN = "NOT_YOUR_TURN"
    POSITION_OCCUPIED = "POSITION_OCCUPIED"
    INVALID_MOVE = "INVALID_MOVE"
    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    BOARD_NOT_FOUND = "BOARD_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class APIResponse(BaseModel):
    ok: bool = True
    code: Optional[ErrorCode] = None
    message: Optional[str] = None
    data: Optional[Any] = None
    meta: Optional[dict] = None

    model_config = dict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )
