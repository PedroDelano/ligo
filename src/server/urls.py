from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("game/", include(("game.urls", "game"), namespace="game")),
    path("home/", include(("main_page.urls", "home"), namespace="home")),
    path(
        "queue/",
        include(("player_queue.urls", "player_queue"), namespace="player_queue"),
    ),
]
