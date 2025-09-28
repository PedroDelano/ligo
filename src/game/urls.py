from django.urls import path

from . import views

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
]
