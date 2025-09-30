from django.conf import settings
from django.db import models

# PositiveSmallIntegerField is in range [0, 32767]


class PlayerRating(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    updated_at = models.DateTimeField(auto_now=True)
    skill_level = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["-updated_at"]


class PlayerQueue(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="queue_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    player_name = models.CharField(max_length=100)
    skill_level = models.PositiveSmallIntegerField()
    board_size = models.PositiveSmallIntegerField(
        choices=[(9, "9x9"), (13, "13x13"), (19, "19x19")]
    )

    class Meta:
        indexes = [
            models.Index(fields=["board_size", "skill_level"], name="idx_board_skill"),
        ]
        # A user cannot be in the queue more than once at a time
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="uq_user_once",
            )
        ]
        ordering = ["created_at"]
