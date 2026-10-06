from src.config import get_settings
from src.services.telegram.bot import DriverOpsBot


def make_telegram_bot() -> DriverOpsBot:
    return DriverOpsBot(get_settings())
