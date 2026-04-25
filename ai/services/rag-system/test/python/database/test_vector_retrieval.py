"""Tests for vector retrieval correctness against pre-seeded data.

Сценарий: заранее заполняем VectorStore фикстурными данными (seed_vectors.json)
и проверяем, что поиск по каждому запросу возвращает именно те чанки,
которые ожидаются — т.е. система не «обманывает», а достаёт правильные документы.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.database.vector_db import SearchResult, VectorStore
from test.resources import load_json


@pytest.fixture
def seed_data():
    """Загружает заранее подготовленные данные для посева в VectorStore."""
    return load_json("request/database/seed_vectors.json")


@pytest.fixture
def seeded_store(seed_data):
    """VectorStore с замоканным Qdrant, который возвращает результаты
    на основе cosine similarity к заранее загруженным векторам."""

    stored_points = []
    for i, vec in enumerate(seed_data["vectors"]):
        stored_points.append({
            "id": f"point-{i}",
            "vector": vec["embedding"],
            "payload": {"text": vec["text"], **vec["metadata"]},
        })

    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def fake_search(collection_name, query_vector, limit=10, score_threshold=0.0):
        scored = []
        for pt in stored_points:
            sim = _cosine_sim(query_vector, pt["vector"])
            if sim >= score_threshold:
                hit = MagicMock()
                hit.id = pt["id"]
                hit.score = sim
                hit.payload = pt["payload"]
                scored.append(hit)
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:limit]

    mock_qdrant = AsyncMock()
    mock_qdrant.search = AsyncMock(side_effect=fake_search)

    with patch("rag.database.vector_db.AsyncQdrantClient", return_value=mock_qdrant):
        store = VectorStore(url="http://test:6333")
        store._client = mock_qdrant
        return store


class TestVectorRetrieval:
    """Проверяем, что поиск по заранее подготовленным запросам
    возвращает именно ожидаемые документы и разделы."""

    async def test_paracetamol_description_query(self, seeded_store, seed_data):
        """Запрос, близкий к описанию парацетамола, должен вернуть doc-paracetamol."""
        q = seed_data["queries"]["paracetamol_description"]
        results = await seeded_store.search("test_col", q["vector"], top_k=3)

        assert len(results) >= 1
        top = results[0]
        assert top.document_id == q["expected_top_document_id"]
        assert "Парацетамол" in top.text

    async def test_contraindications_query(self, seeded_store, seed_data):
        """Запрос о противопоказаниях должен вернуть чанк с противопоказаниями."""
        q = seed_data["queries"]["contraindications"]
        results = await seeded_store.search("test_col", q["vector"], top_k=3)

        assert len(results) >= 1
        top = results[0]
        assert top.document_id == q["expected_top_document_id"]
        assert q["expected_top_section"] in str(top.metadata.get("section_path", []))

    async def test_ibuprofen_dosage_query(self, seeded_store, seed_data):
        """Запрос о дозировке ибупрофена должен вернуть doc-ibuprofen/Дозировка."""
        q = seed_data["queries"]["ibuprofen_dosage"]
        results = await seeded_store.search("test_col", q["vector"], top_k=3)

        assert len(results) >= 1
        top = results[0]
        assert top.document_id == q["expected_top_document_id"]
        assert "Дозировка" in str(top.metadata.get("section_path", []))

    async def test_top_result_has_highest_score(self, seeded_store, seed_data):
        """Результаты должны быть отсортированы по убыванию score."""
        q = seed_data["queries"]["paracetamol_description"]
        results = await seeded_store.search("test_col", q["vector"], top_k=5)

        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    async def test_all_results_are_search_result_type(self, seeded_store, seed_data):
        """Все элементы результата — экземпляры SearchResult."""
        q = seed_data["queries"]["paracetamol_description"]
        results = await seeded_store.search("test_col", q["vector"], top_k=5)

        assert all(isinstance(r, SearchResult) for r in results)

    async def test_different_queries_return_different_top_docs(self, seeded_store, seed_data):
        """Разные запросы должны возвращать разные top-1 документы —
        система не возвращает один и тот же результат на всё."""
        top_docs = []
        for query_name in seed_data["queries"]:
            q = seed_data["queries"][query_name]
            results = await seeded_store.search("test_col", q["vector"], top_k=1)
            assert len(results) == 1
            top_docs.append((results[0].document_id, results[0].metadata.get("section_path")))

        # Должно быть хотя бы 2 уникальных (document_id, section_path) пары
        assert len(set(str(d) for d in top_docs)) >= 2

    async def test_seed_data_all_documents_reachable(self, seeded_store, seed_data):
        """Каждый документ из seed data должен быть достижим хотя бы одним запросом."""
        all_doc_ids = {v["metadata"]["document_id"] for v in seed_data["vectors"]}
        found_doc_ids = set()

        for query_name in seed_data["queries"]:
            q = seed_data["queries"][query_name]
            results = await seeded_store.search(
                "test_col", q["vector"], top_k=5, score_threshold=0.5
            )
            for r in results:
                found_doc_ids.add(r.document_id)

        assert all_doc_ids.issubset(found_doc_ids), (
            f"Не все документы доступны через поиск: "
            f"missing={all_doc_ids - found_doc_ids}"
        )
