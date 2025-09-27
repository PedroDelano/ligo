from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "new/<str:player1>/<str:player2>/<int:board_size>/",
        views.new_game,
        name="new_game",
    ),
    path("delete/<int:game_id>/", views.delete_game, name="delete_game"),
]
