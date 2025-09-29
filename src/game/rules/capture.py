from typing import List, Tuple

from .groups import Groups
from .models import Game, Move, StoneColor


class Capture:
    @classmethod
    def remove_captured_stones(cls, game: Game) -> Tuple[Game, List[Move]]:
        assert isinstance(game, Game)
        captured_stones: List[Move] = []

        if len(game.moves) == 0:
            return game, captured_stones

        groups = Groups.get_groups(game, StoneColor.BLACK) + Groups.get_groups(
            game, StoneColor.WHITE
        )

        moves = []
        for group in groups:
            if group.alive:
                moves.extend(group.stones)
            else:
                captured_stones.extend(group.stones)

        assert all(isinstance(m, Move) for m in moves)
        assert all(isinstance(m, Move) for m in captured_stones)
        return Game(board=game.board, moves=moves), captured_stones
