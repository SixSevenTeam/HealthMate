"""Offline indexer: читает Vidal HTML, строит JSON-дерево и загружает dense-вектора в Qdrant.

В payload каждого чанка сохраняется `sparse_text`, чтобы BM25-слой можно было
восстановить из Qdrant без отдельного хранилища.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Iterable

from rag.core.config import settings
from rag.core.embeddings import get_embedding_service
from rag.database.vector_db import VectorStore
from rag.parsing import MarkdownTreeBuilder, Processor
from rag.parsing.html_parser import is_indication_heading
from rag.retrieval.chunking import get_chunker
from rag.retrieval.sparse import normalize_for_sparse

log = logging.getLogger(__name__)


def _prune_tree_to_indications(node: dict[str, object]) -> dict[str, object] | None:
    """Оставляет в дереве только ветки с разделом показаний.

    Сохраняем предков, чтобы section_path оставался понятным, но чистим их content,
    чтобы в recommendation-коллекцию не попадали побочные действия и противопоказания.
    """
    children = []
    for child in node.get("children", []):
        pruned_child = _prune_tree_to_indications(child)
        if pruned_child is not None:
            children.append(pruned_child)

    heading = node.get("heading", {}) or {}
    title = str(heading.get("title", ""))
    keep_self = node.get("type") == "root" or is_indication_heading(title) or bool(children)
    if not keep_self:
        return None

    pruned = dict(node)
    if node.get("type") == "root":
        pruned["content"] = ""
    elif is_indication_heading(title):
        pruned["content"] = str(node.get("content") or "")
    else:
        pruned["content"] = ""
    pruned["children"] = children
    return pruned


def _iter_documents(dataset_root: str) -> Iterable[Path]:
    """Возвращает HTML-файлы для индексирования."""
    root = Path(dataset_root)

    for pattern in ("*.htm", "*.html", "*.xhtml"):
        yield from sorted(root.rglob(pattern))


async def index_dataset() -> None:
    """Main entry: индексирует датасет и загружает в Qdrant."""
    dataset_root = settings.dataset_root
    dataset_path = Path(dataset_root)

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset root not found: {dataset_root}")

    log.info("indexing_start", dataset=dataset_root)

    embedder = get_embedding_service()
    qdrant = VectorStore(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    await qdrant.create_collection_if_not_exists(
        collection=settings.qdrant_collection_name,
        dimension=settings.embedding_dimension,
    )

    processor = Processor()
    tree_builder = MarkdownTreeBuilder()
    chunker = get_chunker()

    texts: list[str] = []
    metadatas: list[dict[str, object]] = []

    for path in _iter_documents(dataset_root):
        doc_id = path.relative_to(dataset_path).as_posix()

        try:
            pages_data = processor.convert_to_markdown(str(path))
            json_tree = tree_builder.build_tree(pages_data)
            indication_tree = _prune_tree_to_indications(json_tree)
            if indication_tree is None:
                log.info("skip_doc_no_indications", path=str(path), document_id=doc_id)
                continue

            chunks = chunker.chunk_document(indication_tree)
        except Exception:
            log.exception("parse_doc_failed", path=str(path))
            continue

        for chunk in chunks:
            sparse_text = normalize_for_sparse(chunk.text)
            texts.append(chunk.text)
            metadatas.append(
                {
                    "document_id": doc_id,
                    "chunk_index": chunk.chunk_index,
                    "section_path": chunk.section_path,
                    "sparse_text": sparse_text,
                    "doc_type": "drug",
                    "section_type": "indications",
                }
            )

            if len(texts) >= settings.embedding_batch_size:
                embeddings = await embedder.embed_batch(texts)
                await qdrant.insert_vectors(
                    collection=settings.qdrant_collection_name,
                    embeddings=embeddings,
                    texts=texts,
                    metadata=metadatas,
                )
                texts.clear()
                metadatas.clear()

    if texts:
        embeddings = await embedder.embed_batch(texts)
        await qdrant.insert_vectors(
            collection=settings.qdrant_collection_name,
            embeddings=embeddings,
            texts=texts,
            metadata=metadatas,
        )

    log.info("indexing_finished")


if __name__ == "__main__":
    asyncio.run(index_dataset())
