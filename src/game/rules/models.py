from enum import Enum
from typing import List

import pydantic

VALID_BOARD_SIZES = [9, 13, 19]


class StoneColor(str, Enum):
    BLACK = "B"
    WHITE = "W"


class Board(pydantic.BaseModel):
    size: int


class Move(pydantic.BaseModel):
    x: int
    y: int
    color: StoneColor
    move_number: int


class Game(pydantic.BaseModel):
    board: Board
    moves: List[Move]


class Group(pydantic.BaseModel):
    stones: List[Move]
    color: StoneColor
    alive: bool
    liberties: int
    size: int
