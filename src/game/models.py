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
    board = models.ForeignKey(Board, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    move_number = models.IntegerField()
    x = models.IntegerField()
    y = models.IntegerField()
    color = models.CharField(max_length=1, choices=[("B", "Black"), ("W", "White")])
