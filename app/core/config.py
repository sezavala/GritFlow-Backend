from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings configuration to load in env variables
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment:  Literal["dev", "prod"] = "dev"
    debug: bool = Field(default=True)
    backend_base_url: str
    frontend_base_url: str

    # database_url: str

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

settings = Settings()