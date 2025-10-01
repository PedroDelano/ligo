from django.contrib.auth import get_user_model
from django.db import models

from game.models import Game

User = get_user_model()


class BotPlayer(models.Model):
    """Represents a bot player"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="bot_profile"
    )
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ("random", "Random"),
            ("simple", "Simple"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
        ],
        default="simple",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.difficulty})"


class BotGame(models.Model):
    game = models.OneToOneField(Game, on_delete=models.CASCADE, related_name="bot_game")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bot_player = models.ForeignKey(BotPlayer, on_delete=models.CASCADE)
    bot_color = models.CharField(max_length=1, choices=[("B", "Black"), ("W", "White")])

    # Removed: status field (use game.status instead)
    # Removed: user_player field (can be derived from game.user_white/user_black)

    def get_user_player(self):
        """Get the human player in this bot game"""
        if self.bot_color == "W":
            return self.game.user_black
        else:
            return self.game.user_white

    def get_bot_user(self):
        """Get the bot's User object"""
        return self.bot_player.user
