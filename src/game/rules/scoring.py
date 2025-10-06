from enum import Enum
from typing import List, Set, Tuple

from game.models import Board

from .models import Game, StoneColor


class TerritoryOwner(str, Enum):
    BLACK = "B"
    WHITE = "W"
    NEUTRAL = "N"  # Dame - contested/neutral points


class Territory:
    """Represents a region of empty intersections"""

    def __init__(self, points: Set[Tuple[int, int]], owner: TerritoryOwner):
        self.points = points
        self.owner = owner
        self.size = len(points)


class Score:
    """Final score for a game"""

    def __init__(
        self,
        board: Board,
        black_stones: int,
        black_territory: int,
        white_stones: int,
        white_territory: int,
        komi: float = 7.5,
    ):
        assert isinstance(black_stones, int)
        assert isinstance(black_territory, int)
        assert isinstance(white_stones, int)
        assert isinstance(white_territory, int)
        assert isinstance(komi, float)

        self.black_stones = black_stones
        self.black_territory = black_territory
        self.white_stones = white_stones
        self.white_territory = white_territory
        self.komi = komi

        self.white_captures = board.white_captures
        self.black_captures = board.black_captures

        self.black_total = black_stones + black_territory
        self.white_total = white_stones + white_territory + komi

        self.winner = (
            StoneColor.BLACK
            if self.black_total > self.white_total
            else StoneColor.WHITE
        )
        self.margin = abs(self.black_total - self.white_total)

    def __repr__(self):
        return (
            f"Black: {self.black_stones} stones + {self.black_territory} territory = {self.black_total}\n"
            f"White: {self.white_stones} stones + {self.white_territory} territory + {self.komi} komi = {self.white_total}\n"
            f"Winner: {self.winner.value} by {self.margin:.1f} points"
        )


class Scoring:
    @classmethod
    def calculate_score(
        cls, game: Game, board: Board, komi: float = 7.5, debug: bool = False
    ) -> Score:
        """
        Calculate the score using Chinese rules.

        Chinese scoring: stones on board + territory controlled
        Territory = empty intersections surrounded by your stones
        """
        assert isinstance(game, Game)
        assert isinstance(komi, float)
        assert isinstance(debug, bool)

        # Get occupied positions
        occupied = {(m.x, m.y): m.color for m in game.moves}

        # Find all territories (empty regions)
        territories = cls._find_territories(game, occupied, debug)

        # Count stones and territory for each player
        black_stones = sum(
            1 for m in game.moves if m.color == StoneColor.BLACK and m.alive
        )
        white_stones = sum(
            1 for m in game.moves if m.color == StoneColor.WHITE and m.alive
        )

        black_territory = sum(
            t.size for t in territories if t.owner == TerritoryOwner.BLACK
        )
        white_territory = sum(
            t.size for t in territories if t.owner == TerritoryOwner.WHITE
        )

        if debug:
            print(f"\nBlack stones: {black_stones}")
            print(f"White stones: {white_stones}")
            print(f"Black territory: {black_territory}")
            print(f"White territory: {white_territory}")
            print(
                f"Neutral points: {sum(t.size for t in territories if t.owner == TerritoryOwner.NEUTRAL)}"
            )

        return Score(
            board, black_stones, black_territory, white_stones, white_territory, komi
        )

    @classmethod
    def _find_territories(
        cls, game: Game, occupied: dict, debug: bool = False
    ) -> List[Territory]:
        """Find all empty regions and determine their ownership"""
        board_size = game.board.size
        visited = set()
        territories = []

        # Check every empty intersection
        for x in range(board_size):
            for y in range(board_size):
                if (x, y) in occupied or (x, y) in visited:
                    continue

                # Flood fill to find the connected empty region
                region, bordering_colors = cls._flood_fill_territory(
                    x, y, board_size, occupied, visited
                )

                # Determine ownership based on bordering colors
                owner = cls._determine_owner(bordering_colors)

                territory = Territory(region, owner)
                territories.append(territory)

                if debug and territory.size > 0:
                    print(
                        f"Territory at {list(region)[:3]}... Size: {territory.size}, Owner: {owner.value}"
                    )

        return territories

    @classmethod
    def _flood_fill_territory(
        cls, start_x: int, start_y: int, board_size: int, occupied: dict, visited: set
    ) -> Tuple[Set[Tuple[int, int]], Set[StoneColor]]:
        """
        Flood fill from a starting empty point to find connected empty region.
        Returns the region and the set of stone colors that border it.
        """
        region = set()
        bordering_colors = set()
        stack = [(start_x, start_y)]

        while stack:
            x, y = stack.pop()

            if (x, y) in visited:
                continue

            if (x, y) in occupied:
                # Hit a stone - record its color
                bordering_colors.add(occupied[(x, y)])
                continue

            # Mark as visited and add to region
            visited.add((x, y))
            region.add((x, y))

            # Check all four adjacent intersections
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < board_size and 0 <= ny < board_size:
                    if (nx, ny) not in visited:
                        stack.append((nx, ny))

        return region, bordering_colors

    @classmethod
    def _determine_owner(cls, bordering_colors: Set[StoneColor]) -> TerritoryOwner:
        """
        Determine who owns a territory based on bordering stone colors.

        - If only black stones border it: Black territory
        - If only white stones border it: White territory
        - If both colors border it: Neutral (dame)
        - If no stones border it: Neutral (shouldn't happen in normal games)
        """
        if len(bordering_colors) == 0:
            return TerritoryOwner.NEUTRAL
        elif len(bordering_colors) == 1:
            color = list(bordering_colors)[0]
            return (
                TerritoryOwner.BLACK
                if color == StoneColor.BLACK
                else TerritoryOwner.WHITE
            )
        else:
            # Both colors border this region - it's neutral
            return TerritoryOwner.NEUTRAL


# Example usage function
# def score_game(game: Game, komi: float = 7.5, debug: bool = False) -> Score:
#     """
#     Convenience function to score a completed game.

#     Args:
#         game: The game state to score
#         komi: Compensation points for white (default 7.5)
#         debug: Print debug information

#     Returns:
#         Score object with detailed results
#     """
#     return Scoring.calculate_score(game, komi, debug)
