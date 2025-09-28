import json
import time

from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import Board, Game, LastMoveCache, Move
from .responses import APIResponse, StoneColor


def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")


@ensure_csrf_cookie
def new_game(request, player1, player2, board_size=19):
    assert isinstance(player1, str)
    assert isinstance(player2, str)
    assert isinstance(board_size, int)
    game = Game.objects.create(user_white=player1, user_black=player2)
    board = Board.objects.create(game=game, size=board_size)
    context = {
        "game_id": game.id,
        "board_id": board.id,
        "player_1": player1,
        "player_2": player2,
        "board_size": board_size,
    }
    template = loader.get_template("game/index.html")
    print(f"New game created: {context}")
    return HttpResponse(template.render(context, request))


def board_state(request, board_id):
    board = Board.objects.only("id", "size").get(id=board_id)
    last = (
        Move.objects.filter(board=board)
        .only("color", "move_number")
        .order_by("-move_number")
        .first()
    )
    next_color = "W" if last and last.color == "B" else "B"
    first_move = last is None

    moves = list(
        Move.objects.filter(board=board)
        .order_by("move_number")
        .values("x", "y", "color", "move_number")
    )

    return JsonResponse(
        APIResponse(
            data={
                "board_id": board.id,
                "size": board.size,
                "moves": moves,
                "next_color": next_color,
                "first_move": first_move,
            }
        ).model_dump()
    )


@require_http_methods(["POST"])
def place_stone(request, board_id, x, y, color):
    color = StoneColor(color)
    board = Board.objects.select_for_update().get(id=board_id)

    if not (0 <= x < board.size and 0 <= y < board.size):
        return JsonResponse(
            APIResponse(
                ok=False,
                code="OUT_OF_BOUNDS",
                message="Invalid move: out of bounds",
            ).model_dump(),
            status=400,
        )

    if Move.objects.filter(board=board, x=x, y=y).exists():
        return JsonResponse(
            APIResponse(
                ok=False,
                code="POSITION_OCCUPIED",
                message="Invalid move: position occupied",
            ).model_dump()
        )

    last = (
        LastMoveCache.objects.select_related("move")
        .filter(board=board)
        .values("move__color", "move__move_number")
        .first()
    )
    if last is not None and last.get("move__color") == color.value:
        return JsonResponse(
            APIResponse(
                ok=False, code="NOT_YOUR_TURN", message="Invalid move: not your turn"
            ).model_dump(),
            status=400,
        )

    next_num = 1 if last is None else last.get("move__move_number") + 1

    # Inserts after validation
    m = Move.objects.create(
        board=board, move_number=next_num, x=x, y=y, color=color.value
    )
    LastMoveCache.objects.update_or_create(
        board=board,
        defaults={"move_id": m.id},
    )

    return JsonResponse(APIResponse(data={"move_number": next_num}).model_dump())
