
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    deepseek_api_key: str = Field(default=False)
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1")
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
    openai_api_key: str = Field(default=False)
    embedding_model: str = Field(default="deepvk/USER-bge-m3")
    embedding_dimension: int = Field(default=1024)

    # Vector Database (Qdrant)
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection_name: str = Field(default="medical_documents")
    qdrant_timeout: int = Field(default=30)

    # Kafka

    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    kafka_input_topic: str = Field(
        default="json-outgoing",
        description="Topic с распарсенными документами от document-parser"
    )
    kafka_status_topic: str = Field(
        default="document.status",
        description="Topic для отправки статусов обработки"
    )
    kafka_consumer_group: str = Field(default="python-group")

    # MinIO / S3
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="admin")
    minio_secret_key: str = Field(default="admin12345")
    minio_secure: bool = Field(default=False)
    minio_input_bucket: str = Field(
        default="processed-json-doc",
        description="Bucket откуда читаем распарсенные JSON"
    )

    # Обработка
    temp_dir: str = Field(
        default="/tmp/jsn-rag",
        description="Каталог для временных json-файлов",
    )

    # Retrieval (поиск)
    retrieval_top_k: int = Field(default=10)
    retrieval_similarity_threshold: float = Field(default=0.7)
    hybrid_search_weight_semantic: float = Field(default=0.7)
    hybrid_search_weight_lexical: float = Field(default=0.3)

    # Chunking

    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=128)
    min_chunk_size: int = Field(default=100)

    # Dialogue (диалог с пользователем)
    max_clarifying_questions: int = Field(default=3)
    anamnesis_timeout_seconds: int = Field(default=300)

    # API

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8001)
    api_workers: int = Field(default=4)
    api_reload: bool = Field(default=True)

    # Логирование
    log_level: str = Field(default="INFO")
    log_format: str = Field(
        default="json",
        description="Формат логов: json | console"
    )
    structlog_dev_mode: bool = Field(default=True)

    # PostgreSQL
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="rag_db")
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="postgres")
    postgres_pool_size: int = Field(default=10)
    postgres_max_overflow: int = Field(default=20)


    # Redis

    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_ttl: int = Field(default=3600)

    # Observability

    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090)
    enable_tracing: bool = Field(default=False)
    jaeger_endpoint: str | None = Field(default=None)


    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }




@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()