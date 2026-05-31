from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):

    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka broker address",
    )
    kafka_consumer_group: str = Field(
        default="python-group",
        description="Consumer group ID",
    )
    kafka_input_topic: str = Field(
        default="json-outgoing",
        description="Topic для исходящих событий после обработки",
    )
    kafka_status_topic: str = Field(
        default="document.status",
        description="Topic для статусных событий (PROCESSING, FAILED, MARKDOWN_READY)",
    )
    kafka_output_topic: str = Field(
        default="json-outgoing",
        description="Topic для итоговых событий, которые читает RAG-сервис",
    )

    minio_endpoint: str = Field(
        default="localhost:9000",
        description="MinIO endpoint (host:port)",
    )
    minio_access_key: str = Field(default="admin")
    minio_secret_key: str = Field(default="admin12345")
    minio_secure: bool = Field(default=False)
    minio_output_bucket: str = Field(
        default="processed-json-doc",
        description="Корзина для результатов обработки",
    )

    temp_dir: str = Field(
        default="/tmp/doc-parser",
        description="Каталог для временных файлов документов",
    )

    log_level: str = Field(default="INFO")
    log_format: str = Field(
        default="json",
        description="Формат логов: json | console",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
