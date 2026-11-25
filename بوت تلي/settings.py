import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int
    database_path: str


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    admin_id = os.getenv("ADMIN_ID", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN غير مضبوط في ملف .env")
    if not admin_id.isdigit():
        raise RuntimeError("ADMIN_ID يجب أن يكون رقماً صحيحاً في ملف .env")
    return Settings(
        bot_token=token,
        admin_id=int(admin_id),
        database_path=os.getenv("DATABASE_PATH", "mikey_bot.sqlite3"),
    )
