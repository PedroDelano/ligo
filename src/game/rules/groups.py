from typing import List, Set, Tuple

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
    def count_liberties_for_group(
        cls, group_stones: List[Move], game: Game
    ) -> Tuple[int, Set[Tuple[int, int]]]:
        """
        Count unique liberties for a group of stones.
        Returns the count and the set of liberty positions.
        """
        assert all(isinstance(stone, Move) for stone in group_stones)
        assert isinstance(game, Game)

        liberty_positions = set()
        occupied_positions = {(m.x, m.y) for m in game.moves}
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        for stone in group_stones:
            for dx, dy in directions:
                nx, ny = stone.x + dx, stone.y + dy
                if 0 <= nx < game.board.size and 0 <= ny < game.board.size:
                    if (nx, ny) not in occupied_positions:
                        liberty_positions.add((nx, ny))

        liberties = len(liberty_positions)
        assert isinstance(liberties, int)
        return liberties, liberty_positions

    @classmethod
    def get_group(cls, game: Game, move: Move) -> Group:
        """
        Find all stones connected to the given move using iterative flood-fill.
        Returns a Group with all connected stones and their liberty count.
        """
        assert isinstance(game, Game)
        assert isinstance(move, Move)
        color = StoneColor(move.color)

        group_stones = []
        visited = set()
        stack = [move]

        # Build a lookup for moves by position for efficiency
        moves_by_position = {(m.x, m.y): m for m in game.moves}

        # Flood-fill to find all connected stones
        while stack:
            current = stack.pop()
            current_pos = (current.x, current.y)

            if current_pos in visited:
                continue

            visited.add(current_pos)
            group_stones.append(current)

            # Check all four adjacent positions
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, ny = current.x + dx, current.y + dy
                adj_pos = (nx, ny)

                # Check if position is on board and not visited
                if 0 <= nx < game.board.size and 0 <= ny < game.board.size:
                    if adj_pos not in visited and adj_pos in moves_by_position:
                        adj_move = moves_by_position[adj_pos]
                        # Add to stack if same color
                        if adj_move.color == color:
                            stack.append(adj_move)

        # Count unique liberties for the entire group
        liberties, _ = cls.count_liberties_for_group(group_stones, game)
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
        """Check if a move at this position is already in any group."""
        assert isinstance(groups, list)
        assert isinstance(move, Move)
        if len(groups) == 0:
            return False
        assert all(isinstance(g, Group) for g in groups)

        move_pos = (move.x, move.y)
        for group in groups:
            for stone in group.stones:
                if (stone.x, stone.y) == move_pos:
                    return True
        return False

    @classmethod
    def get_groups(cls, game: Game, color: StoneColor) -> List[Group]:
        """
        Get all groups of the specified color.
        Handles cases where game.moves might contain multiple moves at the same position
        by only considering the most recent move at each position.
        """
        assert isinstance(game, Game)
        color = StoneColor(color)

        current_board_state = {}
        for move in game.moves:
            pos = (move.x, move.y)
            if (
                pos not in current_board_state
                or move.move_number > current_board_state[pos].move_number
            ):
                current_board_state[pos] = move

        # Get all moves of the specified color from current board state
        current_moves = [m for m in current_board_state.values() if m.color == color]

        groups = []
        for move in current_moves:
            if cls.move_already_grouped(move, groups):
                continue
            group = cls.get_group(game, move)
            if group is None:
                continue
            groups.append(group)
        assert all(isinstance(g, Group) for g in groups)
        return groups
