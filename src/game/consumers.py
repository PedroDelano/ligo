from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from bot.models import BotGame

from .models import Board


def group_name(board_id: int) -> str:
    return f"board_{board_id}"


class BoardConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.board_id = int(self.scope["url_route"]["kwargs"]["board_id"])
        self.group = group_name(self.board_id)

        # Authorization: only participants can connect (tweak as needed)
        allowed = await self._user_can_join(self.board_id)
        if not allowed:
            await self.close(code=4403)  # forbidden
            return

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    # Event handler name must match "type" with dots -> underscores
    async def board_update(self, event):
        # event example: {"type": "board.update", "payload": {...}}
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _user_can_join(self, board_id: int) -> bool:
        user = self.scope.get("user", AnonymousUser())
        try:
            b = Board.objects.filter(id=board_id).select_related("game").get()
        except Board.DoesNotExist:
            return False

        if not user.is_authenticated:
            return False

        # Check if user is a player
        if user in (b.game.user_white, b.game.user_black):
            return True

        # Also allow if one of the players is a bot (for bot games)
        # In bot games, the human player should be able to connect
        try:
            bot_game = BotGame.objects.filter(game=b.game).first()
            if bot_game:
                return user == bot_game.get_user_player()
        except Exception:
            pass

        return False
