from enum import Enum

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class GAME_STATUS(Enum):
    ONGOING = "ONGOING"
    WHITE_WON = "WHITE_WON"
    BLACK_WON = "BLACK_WON"
    DRAW = "DRAW"
    ABORTED = "ABORTED"


class Game(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    user_white = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="games_as_white",
    )
    user_black = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="games_as_black",
    )

    status = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.name) for tag in GAME_STATUS],
        default=GAME_STATUS.ONGOING.value,
    )


class Board(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    size = models.IntegerField(
        default=19,
        choices=[(9, "9x9"), (13, "13x13"), (19, "19x19")],
    )


class Move(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    move_number = models.IntegerField()
    x = models.IntegerField()
    y = models.IntegerField()
    color = models.CharField(max_length=1, choices=[("B", "Black"), ("W", "White")])
    alive = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["board", "move_number"], name="uniq_move_number_per_board"
            ),
        ]
        indexes = [
            models.Index(fields=["board", "x", "y"], name="idx_board_xy"),
            models.Index(
                fields=["board", "-move_number"], name="idx_board_lastmove_desc"
            ),
        ]


class LastMoveCache(models.Model):
    board = models.OneToOneField(Board, on_delete=models.CASCADE, primary_key=True)
    move = models.OneToOneField(Move, on_delete=models.CASCADE)
