from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""

    # Claude
    anthropic_api_key: str = ""

    # Blockchain APIs
    etherscan_api_key: str = ""
    bscscan_api_key: str = ""
    solscan_api_key: str = ""
    tronscan_api_key: str = ""
    blockchair_api_key: str = ""

    # Twitter
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""

    # News digest
    news_sources: str = ""  # comma-separated URLs of RSS/HTML sources
    digest_morning_hour: int = 9   # UTC hour for morning digest
    digest_evening_hour: int = 18  # UTC hour for evening digest

    # App
    database_url: str = "sqlite+aiosqlite:///./txpeek.db"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
