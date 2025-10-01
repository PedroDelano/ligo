from django.urls import path
from . import views

app_name = "bot"

urlpatterns = [
    path(
        "new/<str:player>/<str:bot_difficulty>/<int:board_size>/<str:player_color>/",
        views.new_bot_game,
        name="new_bot_game",
    ),
]
