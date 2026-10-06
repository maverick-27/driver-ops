"""Telegram bot: one long-polling process, its own Compose service. It calls the API's agent endpoint,
so every driver question goes through the scope check, and there is exactly one poller per token.

Run: python -m src.services.telegram.bot
"""

import asyncio
import html
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

HEARTBEAT_FILE = Path("/tmp/bot-heartbeat")
MAX_QUESTION_CHARS = 1000

WELCOME = (
    "Hi, I'm Driver Ops. Ask me about trucking rules or Maple Freight procedures, for example:\n"
    "• can i use the fuel card for food\n"
    "• my ELD stopped working\n"
    "• what paperwork do i need to cross into the US\n\n"
    "I answer only from company and regulation documents and show which ones I used. "
    "In an emergency call 911 first, then Dispatch at 905-555-0100."
)
NOT_ALLOWED = "This bot is for Maple Freight drivers. Ask Dispatch to add your Telegram account."
UNAVAILABLE = "I can't answer right now. If it is urgent, call Dispatch at 905-555-0100 (24/7)."


def format_reply(data: dict[str, Any]) -> str:
    """Answer plus the cited documents, as Telegram HTML."""
    text = html.escape(data.get("answer", "").strip())
    sources = data.get("sources") or []
    if sources:
        lines = []
        for source in sources:
            kind = "company policy" if source.get("doc_type") == "company_policy" else f"regulation, {source.get('jurisdiction', '')}"
            title = html.escape(source.get("title", ""))
            url = source.get("source_url")
            label = f'<a href="{html.escape(url, quote=True)}">{title}</a>' if url else title
            lines.append(f"[{html.escape(source['doc_id'])}] {label} ({html.escape(kind)})")
        text += "\n\n<b>Sources</b>\n" + "\n".join(lines)
    return text


class DriverOpsBot:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None):
        self.settings = settings.telegram
        self.allowed_ids = self.settings.allowed_ids
        headers = {"X-API-Key": settings.api_key} if settings.api_key else {}
        self.http = http_client or httpx.AsyncClient(base_url=self.settings.api_base_url, headers=headers, timeout=180)
        # chat id -> (previous question, time asked); lets a follow-up ("does that change in the US") be understood.
        self._last_question: dict[int, tuple[str, float]] = {}

    def is_allowed(self, update: Update) -> bool:
        user = update.effective_user
        return user is not None and user.id in self.allowed_ids

    def _previous_question(self, chat_id: int) -> str | None:
        entry = self._last_question.get(chat_id)
        if entry and time.time() - entry[1] <= self.settings.history_ttl_seconds:
            return entry[0]
        return None

    async def answer(self, chat_id: int, question: str) -> str:
        body = {"query": question, "previous_question": self._previous_question(chat_id)}
        try:
            response = await self.http.post("/api/v1/ask-agentic", json=body)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("API call failed: %s", e)
            return UNAVAILABLE
        data = response.json()
        if not data.get("refused"):
            self._last_question[chat_id] = (question, time.time())
        return format_reply(data)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        await update.message.reply_text(WELCOME if self.is_allowed(update) else NOT_ALLOWED)

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or not update.message.text:
            return
        if not self.is_allowed(update):
            logger.warning("Rejected message from user id %s", update.effective_user.id if update.effective_user else None)
            await update.message.reply_text(NOT_ALLOWED)
            return
        question = update.message.text.strip()[:MAX_QUESTION_CHARS]
        await update.message.chat.send_action(ChatAction.TYPING)
        reply = await self.answer(update.message.chat_id, question)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    async def _heartbeat_loop(self) -> None:
        """Touch a file while the event loop is alive; the container healthcheck reads its age."""
        while True:
            HEARTBEAT_FILE.touch()
            await asyncio.sleep(30)

    async def _post_init(self, application: Application) -> None:
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def build_application(self) -> Application:
        application = Application.builder().token(self.settings.bot_token).post_init(self._post_init).build()
        application.add_handler(CommandHandler(["start", "help"], self.start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message))
        return application


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines include the bot token in the URL
    settings = get_settings()
    if not (settings.telegram.enabled and settings.telegram.bot_token):
        raise SystemExit("Telegram bot is not configured: set TELEGRAM__ENABLED=true and TELEGRAM__BOT_TOKEN")
    if not settings.telegram.allowed_ids:
        logger.warning("TELEGRAM__ALLOWED_USER_IDS is empty: every message will be rejected")
    bot = DriverOpsBot(settings)
    application = bot.build_application()
    application.run_polling(allowed_updates=[Update.MESSAGE])


if __name__ == "__main__":
    main()
