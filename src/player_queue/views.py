from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.template import loader
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from game.models import GAME_STATUS, Board, Game

from .models import PlayerQueue, PlayerRating


def create_game(player1, player2, board_size):
    game = Game.objects.create(user_white=player1.username, user_black=player2.username)
    _ = Board.objects.create(game=game, size=board_size)
    return game.id


@require_http_methods(["POST"])
@transaction.atomic
def add_player_to_queue(request):
    template = loader.get_template("player_queue/index.html")
    user = request.user
    if not user.is_authenticated:
        return HttpResponse("Unauthorized", status=401)

    # Check if player is in a game
    ongoing_game = (
        Game.objects.filter(
            user_white=user.username, status=GAME_STATUS.ONGOING
        ).exists()
        or Game.objects.filter(
            user_black=user.username, status=GAME_STATUS.ONGOING
        ).exists()
    )
    if ongoing_game:
        game_id = (
            Game.objects.filter(user_white=user.username)
            .values_list("id", flat=True)
            .first()
            or Game.objects.filter(user_black=user.username)
            .values_list("id", flat=True)
            .first()
        )
        return redirect(reverse("game:get_game", kwargs={"game_id": game_id}))

    player_name = (request.POST.get("player_name") or "").strip()
    try:
        board_size = int(request.POST.get("board_size", "0"))
    except ValueError:
        return HttpResponseBadRequest("Invalid board size")

    if board_size not in (9, 13, 19):
        return HttpResponseBadRequest("Invalid board size")

    # Get the user's rating (default to 1000 if none)
    rating_obj = PlayerRating.objects.filter(user=user).first()
    user_skill = getattr(rating_obj, "skill_level", 400)

    # Ensure the user is queued exactly once, with normalized data
    pq, created = PlayerQueue.objects.get_or_create(
        user=user,
        defaults={
            "player_name": player_name or user.username,
            "skill_level": user_skill,
            "board_size": board_size,
        },
    )
    # If already present, keep their latest preferences in sync
    if not created:
        if (
            pq.player_name != player_name and player_name
        ) or pq.board_size != board_size:
            pq.player_name = player_name or pq.player_name
            pq.board_size = board_size
            pq.skill_level = user_skill
            pq.save(update_fields=["player_name", "board_size", "skill_level"])

    me_locked = (
        PlayerQueue.objects.select_for_update()
        .filter(user=user, board_size=board_size)
        .first()
    )
    if not me_locked:
        return redirect("player_queue:index")

    low = user_skill - 100
    high = user_skill + 100

    # Lock a compatible opponent; skip rows already locked by another txn
    opponent = (
        PlayerQueue.objects.select_for_update(skip_locked=True)
        .filter(board_size=board_size)
        .exclude(user=user)
        .filter(skill_level__gte=low, skill_level__lte=high)
        .order_by("created_at")
        .first()
    )

    if not opponent:
        context = {
            "message": "You have been added to the queue. Waiting for a match..."
        }
        return HttpResponse(template.render(context, request))

    opponent_user = opponent.user
    opponent.delete()
    me_locked.delete()

    game_id = create_game(
        player1=user,
        player2=opponent_user,
        board_size=board_size,
    )
    print(f"Matched {user.username} vs {opponent_user.username} in game {game_id}")

    return redirect(reverse("game:get_game", kwargs={"game_id": game_id}))
