from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "new/<str:player1>/<str:player2>/<int:board_size>/",
        views.new_game,
        name="new_game",
    ),
    path(
        "place/<int:board_id>/<int:x>/<int:y>/<str:color>/",
        views.place_stone,
        name="place_stone",
    ),
    path("board/<int:board_id>/", views.board_state, name="board_state"),
    path("<int:game_id>/", views.get_game, name="get_game"),
]
