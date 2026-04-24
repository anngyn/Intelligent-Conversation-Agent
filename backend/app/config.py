from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    backend_root: Path = Path(__file__).resolve().parents[1]
    app_root: Path = (
        backend_root.parent if (backend_root.parent / "dataset").exists() else backend_root
    )

    # AWS Configuration
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    dynamodb_endpoint_url: str = ""

    # FAISS Configuration
    faiss_index_path: str = str(app_root / "dataset" / "processed" / "faiss_index")

    # Conversation history storage
    conversation_storage_backend: str = "dynamodb"
    conversation_table_name: str = ""
    conversation_ttl_days: int = 7

    # Order / customer operations storage
    order_storage_backend: str = "postgres"
    order_database_url: str = ""
    order_seed_on_startup: bool = False
    order_seed_file_path: str = str(app_root / "dataset" / "mock" / "orders.json")
    pii_hash_salt: str = "dev-only-salt-change-me"

    # API Configuration
    api_title: str = "Agentic Conversational API"
    api_version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]

    # Logging
    log_level: str = "INFO"


settings = Settings()
