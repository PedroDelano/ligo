from django.urls import path

from . import views

app_name = "player_queue"

urlpatterns = [
    path("add/", views.add_player_to_queue, name="add"),
]
