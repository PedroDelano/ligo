from django.shortcuts import render

from player_queue.models import PlayerRating
from player_queue.views import get_queue_counts


def index(request):
    context = {}
    if request.user.is_authenticated:
        current_rating = PlayerRating.objects.filter(user=request.user).first()
        rating_history = PlayerRating.objects.filter(user=request.user).order_by(
            "updated_at"
        )
        context["current_rating"] = current_rating
        context["rating_history"] = rating_history
    context["queue_counts"] = get_queue_counts()
    return render(request, "main_page/home.html", context)
