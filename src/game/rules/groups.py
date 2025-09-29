from typing import List

from .models import Game, Group, Move, StoneColor


class Groups:
    @classmethod
    def is_alive(cls, liberties: int) -> bool:
        assert isinstance(liberties, int)
        return liberties > 0

    @classmethod
    def is_adjacent(cls, a: Move, b: Move) -> bool:
        assert isinstance(a, Move)
        assert isinstance(b, Move)
        if a.x == b.x and abs(a.y - b.y) == 1:
            return True
        if a.y == b.y and abs(a.x - b.x) == 1:
            return True
        return False

    @classmethod
    def count_liberty(cls, move: Move, game: Game) -> int:
        assert isinstance(move, Move)
        assert isinstance(game, Game)
        liberties = 0
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        occupied_positions = {(m.x, m.y) for m in game.moves}

        for dx, dy in directions:
            nx, ny = move.x + dx, move.y + dy
            if 0 <= nx < game.board.size and 0 <= ny < game.board.size:
                if (nx, ny) not in occupied_positions:
                    liberties += 1

        assert isinstance(liberties, int)
        return liberties

    @classmethod
    def get_group(cls, game: Game, move: Move) -> Group:
        assert isinstance(game, Game)
        assert isinstance(move, Move)
        color = StoneColor(move.color)

        group_stones = [move]
        liberties: int = cls.count_liberty(move, game)

        for other_move in game.moves:
            if other_move == move:
                continue
            if other_move.color == color and cls.is_adjacent(move, other_move):
                group_stones.append(other_move)
                liberties += cls.count_liberty(other_move, game)

        alive = cls.is_alive(liberties)
        return Group(
            stones=group_stones,
            color=color,
            alive=alive,
            liberties=liberties,
            size=len(group_stones),
        )

    @classmethod
    def move_already_grouped(cls, move: Move, groups: List[Group]) -> bool:
        assert isinstance(groups, list)
        assert isinstance(move, Move)
        if len(groups) == 0:
            return False
        assert all(isinstance(g, Group) for g in groups)
        for group in groups:
            if move in group.stones:
                return True
        return False

    @classmethod
    def get_groups(cls, game: Game, color: StoneColor) -> List[Group]:
        assert isinstance(game, Game)
        color = StoneColor(color)
        groups = []
        for move in game.moves:
            if move.color != color:
                continue
            if cls.move_already_grouped(move, groups):
                continue
            group = cls.get_group(game, move)
            if group is None:
                continue
            groups.append(group)
        assert all(isinstance(g, Group) for g in groups)
        return groups
