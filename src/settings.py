from pydantic_settings import BaseSettings
from dotenv import load_dotenv


class Settings(BaseSettings):
    PACHI_PATH: str
    DJANGO_SETTINGS_MODULE: str


load_dotenv()
settings = Settings()
