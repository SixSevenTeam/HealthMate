
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


def _find_env_file() -> Path | None:
    """Ищет .env файл начиная от текущего скрипта вверх по дереву."""
    current = Path(__file__).resolve().parent
    # Ищем до 10 уровней вверх
    for _ in range(10):
        env_file = current / ".env"
        if env_file.exists():
            return env_file
        if current.parent == current:  # Дошли до корня
            break
        current = current.parent
    return None


class Settings(BaseSettings):

    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com")
    llm_model: str = Field(default="deepseek-chat")
    llm_temperature: float = Field(default=0.7)
    llm_max_tokens: int = Field(default=4000)

    service_name: str = Field(default="rag-system")
    service_version: str = Field(default="0.1.0")
    environment: Literal["dev", "staging", "prod"] = Field(default="dev")

    # Embeddings (OpenAI)
    embedding_provider: Literal["openai", "cohere", "huggingface"] = Field(
        default="openai"
    )
    openai_api_key: str = Field(default="")
    embedding_model: str = Field(default="deepvk/USER-bge-m3")
    embedding_dimension: int = Field(default=1024)

    # Vector Database (Qdrant)
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection_name: str = Field(default="drug_indications_recommendations")
    qdrant_timeout: int = Field(default=30)

    # Retrieval (поиск)
    retrieval_top_k: int = Field(default=10)
    retrieval_similarity_threshold: float = Field(default=0.7)
    hybrid_search_weight_semantic: float = Field(default=0.7)
    hybrid_search_weight_lexical: float = Field(default=0.3)

    # Chunking
    embedding_batch_size: int = Field(default=100)
    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=128)
    min_chunk_size: int = Field(default=100)

    # Dialogue (диалог с пользователем)
    max_clarifying_questions: int = Field(default=3)
    anamnesis_timeout_seconds: int = Field(default=300)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=1)
    api_reload: bool = Field(default=True)
    internal_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "PYTHON_INTERNAL_API_KEY",
            "INTERNAL_API_KEY",
            "HEALTHMATE_INTERNAL_KEY",
        ),
    )

    # Логирование
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", description="Формат логов: json | console")
    structlog_dev_mode: bool = Field(default=True)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    redis_ttl: int = Field(default=3600)

    # Dataset root for local indexing (mounted from docker-compose)
    dataset_root: str = Field(default="/app/dataset/healthmate_2018-2023/data")

    # Backend (Java) URL — used to resolve drugs and media
    backend_url: str = Field(default="http://localhost:8080", validation_alias="BACKEND_URL")
    # Backend authentication (optional). If set, client will send header
    # `backend_auth_header_name: backend_auth_token` with requests to backend.
    backend_auth_header_name: str = Field(default="Authorization")
    backend_auth_token: str = Field(default="", validation_alias="BACKEND_AUTH_TOKEN")
    # Observability
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090)
    enable_tracing: bool = Field(default=False)
    jaeger_endpoint: str | None = Field(default=None)
    
    model_config = {
        "env_file": _find_env_file(),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }




@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()