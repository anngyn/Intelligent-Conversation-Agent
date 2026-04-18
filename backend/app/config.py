from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS Configuration
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    # FAISS Configuration
    faiss_index_path: str = "dataset/processed/faiss_index"

    # API Configuration
    api_title: str = "Agentic Conversational API"
    api_version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]

    # Logging
    log_level: str = "INFO"


settings = Settings()
