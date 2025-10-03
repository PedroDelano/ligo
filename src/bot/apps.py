# bot/apps.py
import atexit
import logging

from django.apps import AppConfig

from bot.engines.cores.pachi import PachiBot

logger = logging.getLogger(__name__)


class BotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bot"

    def ready(self):
        """Register cleanup handlers when app is ready"""
        atexit.register(self.cleanup_pachi_engines)
        logger.info("Registered Pachi cleanup handler")

    @staticmethod
    def cleanup_pachi_engines():
        """Clean up Pachi engine processes"""
        try:
            PachiBot.cleanup_pools()
            logger.info("Successfully cleaned up Pachi engine pools")
        except Exception as e:
            logger.error(f"Error cleaning up Pachi engine pools: {e}")
