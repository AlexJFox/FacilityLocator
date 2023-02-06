import sys
import asyncio
import logging
from logging import LogRecord, Handler
from logging.config import dictConfig
from pathlib import Path
from collections import deque

from discord import utils

from bot import FacilityBot
from cogs.utils.context import GuildInteraction


class LogRecordContext(LogRecord):
    ctx: GuildInteraction


class ExtraInfoFileHandler(logging.FileHandler):
    def format(self, record: LogRecordContext) -> str:
        ctx = record.ctx
        formatted_record = super().format(record)
        formatted_record += f" in {ctx.guild_id} ({ctx.guild.name})"
        return formatted_record


class GuildHandler(Handler):
    def emit(self, record: LogRecordContext) -> None:
        """Add log record to the guild

        Args:
            record (LogRecordContext): Record to add
        """
        ctx = record.ctx
        guild_deque = ctx.client.guild_logs.get(ctx.guild_id, deque(maxlen=50))

        formatted_record = self.format(record)
        guild_deque.append(formatted_record)

        ctx.client.guild_logs[ctx.guild_id] = guild_deque


class NoVoiceFilter(logging.Filter):
    def filter(self, record):
        return not record.getMessage().startswith("PyNaCl")


class FilterLevel(logging.Filter):
    def __init__(self, *, level) -> None:
        super().__init__()
        self.level = getattr(logging, level)

    def filter(self, record):
        return record.levelno <= self.level


class ConsoleHandler(logging.StreamHandler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.stream = sys.stderr
        else:
            self.stream = sys.stdout
        super().emit(record)


# set log directory
LOG_DIR = Path() / "logs"
LOG_DIR.mkdir(exist_ok=True)

# setup logging config
logging_dict = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "[{asctime}] [{levelname:<8}] {name}: {message}",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "style": "{",
        },
        "slim": {
            "format": "[{asctime}] {name}: {message}",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "style": "{",
        },
        "notime": {
            "format": "[{levelname:<8}] {name}: {message}",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "style": "{",
        },
        "discord_message": {
            "format": "{message} <t:{created:.0f}:R>",
            "style": "{",
        },
    },
    "handlers": {
        "discord_log": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "discord.log",
            "encoding": "utf-8",
            "mode": "w",
            "formatter": "default",
            "filters": ["no_voice_warning"],
        },
        "bot_log": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "bot.log",
            "encoding": "utf-8",
            "mode": "w",
            "formatter": "default",
        },
        "guild_event_log": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "guild.log",
            "encoding": "utf-8",
            "mode": "a",
            "formatter": "slim",
        },
        "facility_event_log": {
            "class": "__main__.ExtraInfoFileHandler",
            "filename": LOG_DIR / "facility.log",
            "encoding": "utf-8",
            "mode": "a",
            "formatter": "slim",
        },
        "guild": {
            "class": "__main__.GuildHandler",
            "formatter": "discord_message",
        },
        "console": {
            "class": "__main__.ConsoleHandler",
            "formatter": "notime",
        },
    },
    "filters": {
        "no_voice_warning": {
            "()": NoVoiceFilter,
        },
    },
    "loggers": {
        "discord": {
            "level": logging.INFO,
            "handlers": ["discord_log"],
            "propagate": False,
        },
        "bot": {
            "level": logging.INFO,
        },
        "cogs": {
            "level": logging.INFO,
        },
        "command_error": {
            "level": logging.INFO,
        },
        "view_error": {
            "level": logging.INFO,
        },
        "modal_error": {
            "level": logging.INFO,
        },
        "guild_event": {
            "level": logging.INFO,
            "handlers": ["guild_event_log"],
            "propagate": False,
        },
        "facility_event": {
            "level": logging.INFO,
            "handlers": ["facility_event_log", "guild"],
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["bot_log", "console"],
    },
}


async def run_bot():
    async with FacilityBot() as bot:
        await bot.start()


def setup_logging():
    dictConfig(logging_dict)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if (
            isinstance(handler, logging.StreamHandler)
            and utils.stream_supports_colour(handler.stream)
            and not isinstance(handler, logging.FileHandler)
        ):
            handler.formatter = utils._ColourFormatter()


if __name__ == "__main__":
    setup_logging()

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass
