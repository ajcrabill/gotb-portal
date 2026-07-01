from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    allowed_embed_origins: list[str] = []

    # Database
    database_url: str

    # Auth
    secret_key: str
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    session_ttl_seconds: int = 86400
    session_ttl_step_up_seconds: int = 3600

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_connect_client_id: str = ""

    # Dropbox Sign — webhook verification uses dropbox_sign_api_key (HMAC), no separate secret
    dropbox_sign_api_key: str = ""
    dropbox_sign_template_id: str = ""   # Practitioner Agreement template ID

    # AI providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Content pipeline
    pipeline_stage2_timeout_seconds: int = 30
    pipeline_stage2_token_ceiling: int = 2000
    pipeline_circuit_breaker_threshold: int = 5

    # AI-ops cost ceilings (USD/day)
    ai_cost_ceiling_content: float = 50.0
    ai_cost_ceiling_transcription: float = 20.0
    ai_cost_ceiling_grader: float = 30.0

    # Email
    postmark_server_token: str = ""
    email_from: str = "portal@gotb.effectiveschoolboards.com"
    bcc_inbound_address: str = "log@gotbindex.com"

    # Backup
    backup_encryption_key: str = ""
    backup_destination: str = ""
    backup_rpo_minutes: int = 60
    backup_rto_minutes: int = 120

    # i18n
    default_locale: str = "en"
    supported_locales: list[str] = ["en", "es"]

    @property
    def allowed_origins(self) -> list[str]:
        origins = [self.frontend_url]
        origins.extend(self.allowed_embed_origins)
        return origins


settings = Settings()
