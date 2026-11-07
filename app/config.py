from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: str = "development"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    database_url: str = "sqlite:///./data/neurotwin.db"
    seed_demo: bool = True
    demo_password: str = ""
    gemini_api_key: str = ""
    meta_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    meta_base_url: str = "https://api.meta.ai/v1"
    ai_enabled: bool = False
    gemini_routine_model: str = "gemini-2.5-flash"
    gemini_camera_model: str = "gemini-2.5-flash"
    gemini_review_model: str = "gemini-2.5-pro"
    meta_draft_model: str = "muse-spark-1.3"
    meta_transcribe_model: str = "muse-voice-transcribe-1.0"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    ai_timeout_seconds: float = 25
    ai_max_calls_per_minute: int = 12
    document_soffice: str = ""
    media_store_path: str = str(ROOT / "data" / "private-messages")
    media_image_mb: int = 8
    media_video_mb: int = 32
    media_audio_mb: int = 12
    media_document_mb: int = 10
    media_message_mb: int = 48
    media_user_quota_mb: int = 256
    media_uploads_per_day: int = 100
    media_scan_executable: str = ""
    media_allow_unscanned_development: bool = True
    media_process_timeout_seconds: int = 60


settings = Settings()
