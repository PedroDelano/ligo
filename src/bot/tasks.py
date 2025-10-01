from celery import shared_task
from bot.services.bot_service import BotService


@shared_task
def trigger_bot_move(board_id: int):
    """Async task to make bot move with slight delay"""
    BotService.make_bot_move(board_id)
