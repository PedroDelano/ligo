from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.http import require_http_methods

from bot.services.bot_service import BotService
from bot.tasks import trigger_bot_move

from .controllers.finish_game import FinishGame
from .controllers.move_validation import MoveValidation
from .models import GAME_STATUS, Board, Game, LastMoveCache, Move
from .responses import APIResponse, ErrorCode
from .rules import capture, models, groups
from .rules.utils import invert_color


def notify_board_update(board, payload: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"board_{board.id}",
        {"type": "board.update", "payload": payload},
    )


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

    # Who am I?
    me = getattr(request.user, "username", None)
    if me == game.user_black.username:
        user_color = "black"
    elif me == game.user_white.username:
        user_color = "white"
    else:
        user_color = "black"

    context = {
        "game_id": game.id,
        "board_id": board.id,
        "player_1": game.user_black.username,
        "player_2": game.user_white.username,
        "board_size": board.size,
        "user_color": user_color,
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
    if not request.user.is_authenticated:
        return JsonResponse(
            APIResponse(
                ok=False, code="UNAUTHORIZED", message="User not authenticated"
            ).model_dump(),
            status=401,
        )
    board = Board.objects.filter(id=board_id).first()
    game = Game.objects.filter(id=board.game_id).first()

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

    game_model = models.Game(
        board=models.Board(size=board.size),
        moves=[models.Move(**move) for move in moves],
    )
    current_game_state, captured_stones = capture.Capture.remove_captured_stones(
        game_model, last_played_color=current_color, invert_color=True
    )
    assert isinstance(current_game_state, models.Game)
    assert all(isinstance(m, models.Move) for m in captured_stones)

    if len(captured_stones) > 0:
        moves = [m.model_dump() for m in current_game_state.moves]
        capture.Capture.mark_captured(board, captured_stones)

    # Include game status and winner information
    game_status = game.status if game else GAME_STATUS.ONGOING.value
    game_ended = game_status != GAME_STATUS.ONGOING.value
    winner = None
    score_data = None
    territory_data = None

    if game_ended:
        score_data, territory_data = FinishGame.get_score_data(board_id)
        score_data = score_data.model_dump()
        territory_data = territory_data.model_dump()

    return JsonResponse(
        APIResponse(
            data={
                "board_id": board.id,
                "size": board.size,
                "moves": moves,
                "next_color": next_color,
                "first_move": first_move,
                "game_ended": game_ended,
                "game_status": game_status,
                "winner": winner,
                "score": score_data,
                "territory": territory_data,
            }
        ).model_dump()
    )


@require_http_methods(["POST"])
@transaction.atomic
def pass_turn(request, board_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            APIResponse(
                ok=False, code="UNAUTHORIZED", message="User not authenticated"
            ).model_dump(),
            status=401,
        )

    move_validation = MoveValidation.is_valid_move(request=request, board_id=board_id)
    if move_validation.is_valid is False:
        return JsonResponse(
            APIResponse(
                ok=False,
                code=move_validation.error_code,
                message="Invalid Move",
            ).model_dump(),
            status=400,
        )

    board = Board.objects.select_for_update().get(id=board_id)
    game = Game.objects.select_for_update().get(id=board.game_id)
    color = move_validation.current_color
    next_num = move_validation.current_move_number + 1

    last = (
        LastMoveCache.objects.select_related("move")
        .filter(board=board)
        .values("move__color", "move__move_number", "move__x", "move__y")
        .first()
    )

    if last is not None and last.get("move__x") == -1 and last.get("move__y") == -1:
        score_data, territory_data = FinishGame.finish_game(board_id)
        notify_board_update(board, {"type": "game_ended"})
        return JsonResponse(
            APIResponse(
                ok=True,
                code="GAME_ENDED",
                message=f"Game ended. {'Black' if game.status == GAME_STATUS.BLACK_WON.value else 'White'} won.",
                data={
                    "game_status": game.status,
                    "game_ended": True,
                    "score": score_data.model_dump(),
                    "territory": territory_data.model_dump(),
                },
            ).model_dump()
        )

    # Inserts after validation
    m = Move.objects.create(
        board=board, move_number=next_num, x=-1, y=-1, color=color.value, alive=True
    )
    LastMoveCache.objects.update_or_create(
        board=board,
        defaults={"move_id": m.id},
    )
    notify_board_update(board, {"type": "pass"})

    # Check if bot should move next - IMPORTANT: Use transaction.on_commit()
    if BotService.is_bot_turn(board_id):
        transaction.on_commit(lambda: trigger_bot_move.delay(board_id))

    return JsonResponse(APIResponse(data={"move_number": next_num}).model_dump())


@require_http_methods(["POST"])
@transaction.atomic
def place_stone(request, board_id, x, y):
    if not request.user.is_authenticated:
        return JsonResponse(
            APIResponse(
                ok=False, code="UNAUTHORIZED", message="User not authenticated"
            ).model_dump(),
            status=401,
        )

    move_validation = MoveValidation.is_valid_move(request=request, board_id=board_id)
    if move_validation.is_valid is False:
        print(f"Invalid mode: {move_validation.error_code}")
        print(BotService.is_bot_turn(board_id))
        return JsonResponse(
            APIResponse(
                ok=False,
                code=move_validation.error_code,
                message="Invalid Move",
            ).model_dump(),
            status=400,
        )

    board = Board.objects.select_for_update().get(id=board_id)
    color = move_validation.current_color
    next_num = move_validation.current_move_number + 1

    moves = list(
        Move.objects.filter(board=board, alive=True)
        .order_by("move_number")
        .values("x", "y", "color", "move_number")
    )
    moves.append(
        models.Move(x=x, y=y, color=color, move_number=len(moves)).model_dump()
    )

    suicide_validation = MoveValidation.is_suicide_move(
        board=board, moves=moves, color=color
    )
    if suicide_validation.is_valid is False:
        return JsonResponse(
            APIResponse(
                ok=False,
                code=move_validation.error_code,
                message="Invalid Move",
            ).model_dump(),
            status=400,
        )

    m = Move.objects.create(
        board=board, move_number=next_num, x=x, y=y, color=color.value
    )
    LastMoveCache.objects.update_or_create(
        board=board,
        defaults={"move_id": m.id},
    )

    notify_board_update(board, {"type": "move"})

    if BotService.is_bot_turn(board_id):
        transaction.on_commit(lambda: trigger_bot_move.delay(board_id))

    return JsonResponse(APIResponse(data={"move_number": next_num}).model_dump())


@transaction.atomic
def resign(request, board_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            APIResponse(
                ok=False, code="UNAUTHORIZED", message="User not authenticated"
            ).model_dump(),
            status=401,
        )

    move_validation = MoveValidation.is_valid_move(request=request, board_id=board_id)
    if (
        move_validation.is_valid is False
        and move_validation.error_code != ErrorCode.NOT_YOUR_TURN
    ):
        print(f"Invalid mode: {move_validation.error_code}")
        print(BotService.is_bot_turn(board_id))
        return JsonResponse(
            APIResponse(
                ok=False,
                code=move_validation.error_code,
                message="Invalid Move",
            ).model_dump(),
            status=400,
        )

    board = Board.objects.select_for_update().get(id=board_id)
    game = Game.objects.select_for_update().get(id=board.game_id)
    score_data, territory_data = FinishGame.finish_game(board_id)

    # Determine winner based on who resigned
    winner_color = "Black" if request.user == game.user_white else "White"
    game_status = (
        GAME_STATUS.BLACK_RESIGNED
        if winner_color == "White"
        else GAME_STATUS.WHITE_RESIGNED
    )

    game.status = game_status.value
    game.save(update_fields=["status"])

    notify_board_update(board, {"type": "game_ended"})
    return JsonResponse(
        APIResponse(
            ok=True,
            code="GAME_ENDED",
            message=f"{winner_color} wins by resignation",
            data={
                "game_status": game_status.value,
                "game_ended": True,
                "score": score_data.model_dump(),
                "territory": territory_data.model_dump(),
                "resign_win": True,
            },
        ).model_dump()
    )
