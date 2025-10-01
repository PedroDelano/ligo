import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")
django.setup()

django_asgi_app = get_asgi_application()

if settings.DEBUG:
    http_app = ASGIStaticFilesHandler(django_asgi_app)
else:
    http_app = django_asgi_app


import game.routing

application = ProtocolTypeRouter(
    {
        "http": http_app,
        "websocket": AuthMiddlewareStack(URLRouter(game.routing.websocket_urlpatterns)),
    }
)
