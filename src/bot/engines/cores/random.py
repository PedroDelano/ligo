import random
from typing import Optional, Tuple

from .base import BotEngine


class RandomBot(BotEngine):
    """Makes random valid moves"""

    def select_move(self, game_state: dict) -> Optional[Tuple[int, int]]:
        board_size = game_state["board_size"]
        moves = game_state["moves"]

        # Get occupied positions
        occupied = {(m["x"], m["y"]) for m in moves if m["x"] != -1}

        # Get all valid positions
        valid_positions = [
            (x, y)
            for x in range(board_size)
            for y in range(board_size)
            if (x, y) not in occupied
        ]

        if not valid_positions:
            return None

        return random.choice(valid_positions)

    def should_pass(self, game_state: dict) -> bool:
        # Random bot passes 5% of the time if no moves left
        return random.random() < 0.15
