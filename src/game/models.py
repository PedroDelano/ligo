from django.db import models


class Game(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_white = models.CharField(max_length=100)
    user_black = models.CharField(max_length=100)


class Board(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    size = models.IntegerField(
        default=19, choices=[(9, "9x9"), (13, "13x13"), (19, "19x19")]
    )


class Move(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    move_number = models.IntegerField()
    x = models.IntegerField()
    y = models.IntegerField()
    color = models.CharField(max_length=1, choices=[("B", "Black"), ("W", "White")])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["board", "x", "y"], name="uniq_move_per_intersection"
            ),
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
