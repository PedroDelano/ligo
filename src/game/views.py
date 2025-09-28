import logging

import pydantic
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import Board, Game, Move
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
    try:
        board = Board.objects.get(id=board_id)
    except Board.DoesNotExist:
        raise Http404("Board not found")

    moves = list(
        Move.objects.filter(board=board)
        .order_by("move_number")
        .values("x", "y", "color", "move_number")
    )
    next_color = "B"
    if moves:
        next_color = "W" if moves[-1]["color"] == "B" else "B"

    first_move = len(moves) == 0

    assert isinstance(board.size, int)
    assert isinstance(board.id, int)
    assert isinstance(moves, list)
    assert isinstance(next_color, str)
    assert isinstance(first_move, bool)

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


@require_http_methods(["POST", "GET"])
@transaction.atomic
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

    existing_move = Move.objects.filter(board=board, x=x, y=y).first()
    if existing_move:
        return JsonResponse(
            APIResponse(
                ok=False,
                code="POSITION_OCCUPIED",
                message="Invalid move: position occupied",
            ).model_dump(),
        )

    last_move = Move.objects.filter(board=board).order_by("-move_number").first()
    if last_move and last_move.color == color.value:
        return JsonResponse(
            APIResponse(
                ok=False,
                code="NOT_YOUR_TURN",
                message="Invalid move: not your turn",
            ).model_dump(),
            status=400,
        )

    next_num = 1 if last_move is None else last_move.move_number + 1
    Move.objects.create(board=board, move_number=next_num, x=x, y=y, color=color.value)
    return JsonResponse(APIResponse(data={"move_number": next_num}).model_dump())
