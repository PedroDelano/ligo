from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PACHI_PATH: str
    PACHI_POOL_SIZE: int
    DJANGO_SETTINGS_MODULE: str


load_dotenv()
settings = Settings()
