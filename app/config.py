from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Meta / WhatsApp Cloud API
    meta_api_token: str = ""
    meta_phone_number_id: str = ""
    meta_waba_business_account_id: str = ""  # WhatsApp Business Account ID
    webhook_verify_token: str = "verify_token"

    # Groq
    groq_api_key: str = ""

    # Admin
    admin_api_key: str = "admin-secret"

    # App
    database_path: str = "data/car_rental.db"
    uploads_dir: str = "uploads"
    log_level: str = "INFO"

    # Derived
    @property
    def whatsapp_api_url(self) -> str:
        return f"https://graph.facebook.com/v21.0/{self.meta_phone_number_id}/messages"

    @property
    def whatsapp_media_url(self) -> str:
        return "https://graph.facebook.com/v21.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
