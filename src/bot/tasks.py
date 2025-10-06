from celery import shared_task

from bot.services.bot_service import BotService
import logging

from bot.engines.cores.pachi import PachiBot

logger = logging.getLogger()


@shared_task
def trigger_bot_move(board_id: int):
    for difficulty, pool in PachiBot._pools.items():
        status = pool.get_pool_status()
        logger.debug(f"Pool status for {difficulty}: {status}")
    BotService.make_bot_move(board_id)
