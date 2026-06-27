from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM — required, no default (env must set)
    llm_base_url: str
    llm_api_key: str
    llm_model: str

    # Jina AI — required
    jina_api_key: str

    # Qdrant — required
    qdrant_url: str

    # Redis — required
    redis_url: str

    # LangFuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""

    # Guardrails
    guardrails_token: str = ""

    # App
    environment: str = "development"
    max_intake_exchanges: int = 2
    session_ttl_minutes: int = 30


settings = Settings()
