from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.functions import Abs
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.template import loader
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from game.models import GAME_STATUS, Board, Game

from .models import PlayerQueue


def _get_ongoing_game_id_for(user):
    return (
        Game.objects.filter(
            status=GAME_STATUS.ONGOING.value,
        )
        .filter(Q(user_white=user) | Q(user_black=user))
        .exclude(bot_game__isnull=False)  # Exclude games with a BotGame relation
        .values_list("id", flat=True)
        .first()
    )


def create_game(player1, player2, board_size):
    game = Game.objects.create(user_white=player1, user_black=player2)
    _ = Board.objects.create(game=game, size=board_size)
    return game.id


def get_queue_counts():
    """
    Returns a dictionary with the number of players waiting in queue for each board size.
    Returns: dict like {9: 3, 13: 5, 19: 12}
    """
    counts = (
        PlayerQueue.objects.values("board_size")
        .annotate(count=Count("id"))
        .order_by("board_size")
    )

    # Convert to dictionary and ensure all board sizes are present
    result = {9: 0, 13: 0, 19: 0}
    for item in counts:
        result[item["board_size"]] = item["count"]

    return result


@require_http_methods(["POST"])
@transaction.atomic
@login_required
def add_player_to_queue(request):
    template = loader.get_template("player_queue/index.html")
    user = request.user

    game_id = _get_ongoing_game_id_for(user)
    if game_id:
        return redirect(reverse("game:get_game", kwargs={"game_id": game_id}))
    try:
        board_size = int(request.POST.get("board_size", "0"))
    except ValueError:
        return HttpResponseBadRequest("Invalid board size")
    if board_size not in (9, 13, 19):
        return HttpResponseBadRequest("Invalid board size")

    me = PlayerQueue.objects.update_or_create(
        user=user,
        defaults={"board_size": board_size, "skill_level": 400},
    )
    context = {
        "message": "You have been added to the queue. Waiting for a match...",
        "board_size": board_size,
        "skill_level": me[0].skill_level,
    }
    return HttpResponse(template.render(context, request))


@require_http_methods(["POST"])
@transaction.atomic
@login_required
def check_queue(request):
    template = loader.get_template("player_queue/index.html")
    user = request.user

    game_id = _get_ongoing_game_id_for(user)
    if game_id:
        return redirect(reverse("game:get_game", kwargs={"game_id": game_id}))

    if not PlayerQueue.objects.filter(user=user.id).exists():
        return HttpResponseBadRequest("User not in queue")

    try:
        board_size = int(request.POST.get("board_size", "0"))
    except ValueError:
        return HttpResponseBadRequest("Invalid board size")
    if board_size not in (9, 13, 19):
        return HttpResponseBadRequest("Invalid board size")

    # Ensure the user is queued and fetch their row (locked)
    try:
        me = PlayerQueue.objects.select_for_update().get(user=user)
    except PlayerQueue.DoesNotExist:
        return HttpResponseBadRequest("User not in queue")

    board_size = me.board_size
    skill_level = me.skill_level

    # Find nearest-skill opponent on same board size, not me (lock & skip locked to avoid races)
    opponent = (
        PlayerQueue.objects.select_for_update(skip_locked=True)
        .filter(board_size=board_size)
        .exclude(user=user)
        .annotate(diff=Abs(F("skill_level") - skill_level))
        .order_by("diff", "created_at")
        .first()
    )

    if not opponent:
        context = {
            "message": "You have been added to the queue. Waiting for a match...",
            "board_size": board_size,
        }
        return HttpResponse(template.render(context, request))

    # Exit both from queue
    opponent.delete()
    me.delete()

    game_id = create_game(
        player1=user,
        player2=opponent.user,
        board_size=board_size,
    )
    print(f"Matched {user.username} vs {opponent.user} in game {game_id}")
    return redirect(reverse("game:get_game", kwargs={"game_id": game_id}))
