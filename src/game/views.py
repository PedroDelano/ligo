from django.http import HttpResponse
from .models import Game, Board, Move
from django.template import loader


def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")


def new_game(request, player1, player2, board_size=19):
    assert isinstance(player1, str)
    assert isinstance(player2, str)
    assert isinstance(board_size, int)
    game = Game.objects.create(user_white=player1, user_black=player2)
    board = Board.objects.create(game=game, size=board_size)
    print(f"Created game {game.id} with board {board.id}")
    context = {"game_id": game.id, "board_id": board.id}
    template = loader.get_template("game/index.html")
    return HttpResponse(template.render(context, request))


def delete_game(request, game_id):
    try:
        game = Game.objects.get(id=game_id)
        game.delete()
        return HttpResponse(f"Deleted game {game_id}")
    except Game.DoesNotExist:
        return HttpResponse(f"Game {game_id} does not exist", status=404)
