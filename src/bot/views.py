from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from bot.models import BotGame, BotPlayer
from game.models import Board, Game
from game.responses import APIResponse
from bot.tasks import trigger_bot_move

User = get_user_model()


@require_http_methods(["POST", "GET"])
@transaction.atomic
def new_bot_game(request, player, bot_difficulty, board_size, player_color):
    """Create a new game against a bot"""

    # Get or create bot user
    bot_username = f"Bot-{bot_difficulty}"
    bot_user, _ = User.objects.get_or_create(
        username=bot_username,
        defaults={"is_active": False},  # Bots aren't real users
    )

    # Get or create bot player profile
    bot_player, _ = BotPlayer.objects.get_or_create(
        user=bot_user, defaults={"difficulty": bot_difficulty}
    )

    # Ensure player is a User instance
    if isinstance(player, str):
        try:
            player = User.objects.get(username=player)
        except User.DoesNotExist:
            return JsonResponse(
                APIResponse(
                    ok=False, code="USER_NOT_FOUND", message="Player not found"
                ).model_dump(),
                status=404,
            )

    # Create game with proper User objects
    if player_color == "B":
        game = Game.objects.create(user_white=bot_user, user_black=player)
        bot_color = "W"
    else:
        game = Game.objects.create(user_white=player, user_black=bot_user)
        bot_color = "B"

    board = Board.objects.create(game=game, size=board_size)
    BotGame.objects.create(game=game, bot_player=bot_player, bot_color=bot_color)

    # If bot plays first, trigger move
    if bot_color == "B":
        trigger_bot_move.delay(board.id)

    return JsonResponse(
        APIResponse(data={"game_id": game.id, "board_id": board.id}).model_dump()
    )
