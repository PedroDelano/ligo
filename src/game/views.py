from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.http import require_http_methods

from .models import Board, Game, LastMoveCache, Move
from .responses import APIResponse
from .rules import capture, models


def index(request):
    template = loader.get_template("game/index.html")
    return HttpResponse(template.render({}, request))


def new_game(request, player1, player2, board_size):
    assert isinstance(player1, str)
    assert isinstance(player2, str)
    assert isinstance(board_size, int)
    assert board_size in models.VALID_BOARD_SIZES
    game = Game.objects.create(user_white=player1, user_black=player2)
    _ = Board.objects.create(game=game, size=board_size)
    return JsonResponse(APIResponse(data={"game_id": game.id}).model_dump())


def get_game(request, game_id):
    game = Game.objects.only("id", "user_white", "user_black").get(id=game_id)
    board = Board.objects.filter(game_id=game_id).only("id", "size").get()
    context = {
        "game_id": game.id,
        "board_id": board.id,
        "player_1": game.user_white,
        "player_2": game.user_black,
        "board_size": board.size,
    }
    template = loader.get_template("game/game.html")
    return HttpResponse(template.render(context, request))


def board_state(request, board_id):
    if not Board.objects.filter(id=board_id).exists():
        return JsonResponse(
            APIResponse(
                ok=False, code="BOARD_NOT_FOUND", message="Board not found"
            ).model_dump(),
            status=404,
        )

    board = Board.objects.filter(id=board_id).first()
    moves = list(
        Move.objects.filter(board=board, alive=True)
        .order_by("move_number")
        .values("x", "y", "color", "move_number")
    )

    first_move = len(moves) == 0
    if first_move:
        next_color = "B"
        current_color = "W"
    else:
        next_color = "B" if moves[-1]["color"] == "W" else "W"
        current_color = moves[-1]["color"]

    game = models.Game(
        board=models.Board(size=board.size),
        moves=[models.Move(**move) for move in moves],
    )
    current_game_state, captured_stones = capture.Capture.remove_captured_stones(
        game, last_played_color=current_color
    )
    assert isinstance(current_game_state, models.Game)
    assert all(isinstance(m, models.Move) for m in captured_stones)

    if len(captured_stones) > 0:
        moves = [m.model_dump() for m in current_game_state.moves]
        capture.Capture.mark_captured(board, captured_stones)

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
@transaction.atomic
def place_stone(request, board_id, x, y, color):
    color = models.StoneColor(color)
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

    if Move.objects.filter(board=board, x=x, y=y, alive=True).exists():
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

    # Check for suicide moves
    moves = list(
        Move.objects.filter(board=board, alive=True)
        .order_by("move_number")
        .values("x", "y", "color", "move_number")
    )
    moves.append(
        models.Move(x=x, y=y, color=color, move_number=len(moves)).model_dump()
    )
    game = models.Game(
        board=models.Board(size=board.size),
        moves=[models.Move(**move) for move in moves],
    )
    _, captured_stones = capture.Capture.remove_captured_stones(
        game, last_played_color="W" if color == "B" else "B"
    )

    if models.Move(**moves[-1]) in captured_stones:
        return JsonResponse(
            APIResponse(
                ok=False, code="INVALID_MOVE", message="Invalid move: suicide move"
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
