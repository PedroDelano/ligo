from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BotEngine(ABC):
    """Base class for bot move selection"""

    def __init__(self, board_size: int, difficulty: str):
        self.board_size = board_size
        self.difficulty = difficulty

    @abstractmethod
    def select_move(self, game_state: dict) -> Optional[Tuple[int, int]]:
        """
        Returns (x, y) for next move, or None to pass
        game_state contains: moves, board_size, captured_stones, etc.
        """
        pass

    @abstractmethod
    def should_pass(self, game_state: dict) -> bool:
        """Determine if bot should pass"""
        pass
