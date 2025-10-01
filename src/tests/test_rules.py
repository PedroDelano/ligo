import uuid
from typing import List, Tuple

from django.contrib.auth import get_user_model
from django.test import TestCase

from game.models import Game, Move
from game.rules import capture, models
from tests.utils import ascii_go_board

User = get_user_model()


# ====================================
# Stone Capture
#
#     0  1  2  3  4  5  6  7  8
#  0  +  +  +  +  +  +  +  +  +
#  1  +  +  W  +  +  +  +  +  +
#  2  +  W  B  W  +  +  +  +  +
#  3  +  +  w  +  +  +  +  +  +
#  4  +  +  +  +  +  +  +  +  +
#  5  +  +  +  +  +  +  +  +  +
#  6  +  +  +  +  +  +  +  +  +
#  7  +  +  +  +  +  +  +  +  +
#  8  +  +  +  +  +  +  +  +  +
# ====================================
# Simple Group Capture
#
#     0  1  2  3  4  5  6  7  8
#  0  +  +  +  +  +  +  +  +  +
#  1  +  +  W  +  +  +  +  +  +
#  2  +  W  B  W  +  +  +  +  +
#  3  +  W  B  B  W  +  +  +  +
#  4  +  +  W  B  W  +  +  +  +
#  5  +  +  +  W  +  +  +  +  +
#  6  +  +  +  +  +  +  +  +  +
#  7  +  +  +  +  +  +  +  +  +
#  8  +  +  +  +  +  +  +  +  +
# ===================================
# Eye Fill (M is last move)
#
#     0  1  2  3  4  5  6  7  8
#  0  +  +  +  +  +  +  +  +  +
#  1  +  +  W  +  +  +  +  +  +
#  2  +  W  B  W  +  +  +  +  +
#  3  +  W  M  B  W  +  +  +  +
#  4  +  +  W  B  W  +  +  +  +
#  5  +  +  +  W  +  +  +  +  +
#  6  +  +  +  +  +  +  +  +  +
#  7  +  +  +  +  +  +  +  +  +
#  8  +  +  +  +  +  +  +  +  +
#
# ===================================
# Square Eye Fill (M is last move)
#
#     0  1  2  3  4  5  6  7  8
#  0  +  +  +  +  +  +  +  +  +
#  1  +  +  W  W  W  +  +  +  +
#  2  +  W  B  B  B  W  +  +  +
#  3  +  W  B  M  B  W  +  +  +
#  4  +  W  B  B  B  W  +  +  +
#  5  +  +  W  W  W  +  +  +  +
#  6  +  +  +  +  +  +  +  +  +
#  7  +  +  +  +  +  +  +  +  +
#  8  +  +  +  +  +  +  +  +  +
#
# ===================================
# Corner Group
#
#     0  1  2  3  4  5  6  7  8
#  0  +  +  +  +  +  +  +  +  +
#  1  W  +  +  +  +  +  +  +  +
#  2  B  W  +  +  +  +  +  +  +
#  3  B  W  +  +  +  +  +  +  +
#  4  B  W  +  +  +  +  +  +  +
#  5  B  B  +  +  +  +  +  +  +
#  6  +  +  +  +  +  +  +  +  +
#  7  +  +  +  +  +  +  +  +  +
#  8  +  +  +  +  +  +  +  +  +
#

CAPTURES = [
    {
        "name": "Stone Capture",
        "moves": [
            (2, 2, "B"),  # Black stone
            (1, 2, "W"),  # White stones surrounding
            (2, 1, "W"),
            (3, 2, "W"),
            (2, 3, "W"),
        ],
        "captured": [(2, 2, "B")],
    },
    {
        "name": "Simple Group Capture",
        "moves": [
            (2, 2, "B"),
            (1, 2, "W"),
            (2, 1, "W"),
            (3, 2, "B"),
            (3, 3, "B"),
            (4, 3, "B"),
            (2, 3, "W"),
            (3, 1, "W"),
            (3, 4, "W"),
            (4, 2, "W"),
            (4, 4, "W"),
            (5, 3, "W"),
        ],
        "captured": [(2, 2, "B"), (3, 2, "B"), (3, 3, "B"), (4, 3, "B")],
    },
    {
        "name": "Eye Fill (M is last move)",
        "moves": [
            (2, 2, "B"),
            (1, 2, "W"),
            (2, 1, "W"),
            (3, 2, "B"),
            (3, 3, "B"),
            (4, 3, "B"),
            (2, 3, "W"),
            (3, 1, "W"),
            (3, 4, "W"),
            (4, 2, "W"),
            (4, 4, "W"),
            (5, 3, "W"),
            (3, 2, "W"),  # Last move (eye fill)
        ],
        "captured": [(2, 2, "B"), (3, 3, "B"), (4, 3, "B")],
    },
    {
        "name": "Square Eye Fill (M is last move)",
        "moves": [
            (2, 2, "B"),
            (2, 3, "B"),
            (2, 4, "B"),  # Inner black stones
            (3, 2, "B"),
            (3, 4, "B"),
            (4, 2, "B"),
            (4, 3, "B"),
            (4, 4, "B"),
            # Surrounding white stones
            (1, 2, "W"),
            (1, 3, "W"),
            (1, 4, "W"),
            (2, 1, "W"),
            (2, 5, "W"),
            (3, 1, "W"),
            (3, 5, "W"),
            (4, 1, "W"),
            (4, 5, "W"),
            (5, 2, "W"),
            (5, 3, "W"),
            (5, 4, "W"),
            # Last move filling the eye (M)
            (3, 3, "W"),
        ],
        "captured": [
            (2, 2, "B"),
            (2, 3, "B"),
            (2, 4, "B"),
            (3, 2, "B"),
            (3, 4, "B"),
            (4, 2, "B"),
            (4, 3, "B"),
            (4, 4, "B"),
        ],
    },
    {
        "name": "Corner Group",
        "moves": [
            # Black corner group
            (0, 2, "B"),
            (0, 3, "B"),
            (0, 4, "B"),
            (0, 5, "B"),
            (1, 5, "B"),
            # White surrounding stones
            (0, 1, "W"),
            (1, 2, "W"),
            (1, 3, "W"),
            (1, 4, "W"),
            # (2, 5, "W"),
        ],
        "captured": [],
    },
]


class RulesTest(TestCase):
    def setUp(self):
        self.size = 9
        alice = User.objects.create(username=uuid.uuid4().hex)
        bob = User.objects.create(username=uuid.uuid4().hex)
        self.game = Game.objects.create(user_white=alice, user_black=bob)
        self.board = self.game.board_set.create(game=self.game, size=self.size)

    @staticmethod
    def _add_move_number(move_set: List[Tuple[int, int, str]], start: int = 1):
        return [(x, y, color, idx) for idx, (x, y, color) in enumerate(move_set, start)]

    def test_capture_scenario(self):
        # Simulate a series of moves leading to a capture

        for test_set in CAPTURES:
            self.setUp()
            move_set = test_set["moves"]
            move_set = self._add_move_number(move_set)

            for x, y, color, idx in move_set:
                Move.objects.create(
                    board=self.board, x=x, y=y, color=color, move_number=idx
                )

            moves = list(
                Move.objects.filter(board=self.board, alive=True)
                .order_by("move_number")
                .values("x", "y", "color", "move_number")
            )
            print("")
            print("State before capture:")
            print(ascii_go_board(moves, size=self.size))

            game = models.Game(
                board=models.Board(size=self.size),
                moves=[
                    models.Move(x=x, y=y, color=color, move_number=idx)
                    for x, y, color, idx in move_set
                ],
            )
            current_game_state, captured_stones = (
                capture.Capture.remove_captured_stones(
                    game, last_played_color=move_set[-1][2], debug=True
                )
            )

            assert isinstance(current_game_state, models.Game)
            assert all(isinstance(m, models.Move) for m in captured_stones)

            capture.Capture.mark_captured(self.board, captured_stones)
            moves = list(
                Move.objects.filter(board=self.board, alive=True)
                .order_by("move_number")
                .values("x", "y", "color", "move_number")
            )
            print("State after capture:")
            print(ascii_go_board(moves, size=self.size))

            assert len(captured_stones) == len(test_set["captured"])
