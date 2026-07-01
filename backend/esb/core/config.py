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
    openrouter_api_key: str = ""
    groq_api_key: str = ""

    # Time Use Evaluation — transcription pipeline
    yt_dlp_path: str = "yt-dlp"
    eval_docs_dir: str = "/app/data/eval-docs"
    eval_tmp_dir: str = "/app/data/eval-tmp"
    # SSH fallback chain for YouTube bot-detection bypass — matches esby-portal's
    # existing production setup (same key, same two machines). Empty host = tier skipped.
    whisper_ssh_key_path: str = ""
    whisper_remote1_host: str = "esblaptop-m4.taild49f53.ts.net"
    whisper_remote1_user: str = "ajc"
    whisper_remote1_venv: str = "/Users/ajc/whisper-venv"
    whisper_remote2_host: str = "nimo-blk-chicago.tail58fc0.ts.net"
    whisper_remote2_user: str = "ajc"
    whisper_remote2_venv: str = "/home/ajc/whisper-venv"

    # Content pipeline
    pipeline_stage2_timeout_seconds: int = 30
    pipeline_stage2_token_ceiling: int = 2000
    pipeline_circuit_breaker_threshold: int = 5

    # Content approval bridge — esby-portal hosts the actual generation/publish
    # engine (site-pipeline) on esbcloud; the portal proxies to it as a trusted
    # internal service. Interim architecture — see plan to consolidate later.
    esby_internal_url: str = "https://esbcloud.taild49f53.ts.net:8443"
    esby_internal_key: str = ""

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
