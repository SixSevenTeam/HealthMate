"""Tests for ChunkingService."""

from __future__ import annotations

import pytest

from rag.retrieval.chunking import Chunk, ChunkingService


class TestChunkingService:

    def setup_method(self):
        self.svc = ChunkingService(chunk_size=200, chunk_overlap=30, min_chunk_size=50)

    def test_chunk_document_basic(self, sample_json_tree):
        chunks = self.svc.chunk_document(sample_json_tree)
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_document_preserves_section_path(self, sample_json_tree):
        chunks = self.svc.chunk_document(sample_json_tree)
        paths = [c.section_path for c in chunks]
        assert any("Состав" in p for p in paths)
        assert any("Показания" in p for p in paths)

    def test_chunk_document_empty_tree(self):
        tree = {"heading": {"title": "Root"}, "content": "", "children": []}
        chunks = self.svc.chunk_document(tree)
        assert chunks == []

    def test_traverse_tree_skips_root_title(self):
        tree = {
            "heading": {"title": "Document Root"},
            "content": "some text",
            "children": [],
        }
        chunks = self.svc._traverse_tree(tree, [])
        assert len(chunks) == 1
        assert chunks[0].section_path == []

    def test_traverse_tree_adds_child_title(self):
        tree = {
            "heading": {"title": "Document Root"},
            "content": "",
            "children": [
                {
                    "heading": {"title": "Section A"},
                    "content": "content A",
                    "children": [],
                }
            ],
        }
        chunks = self.svc._traverse_tree(tree, [])
        assert chunks[0].section_path == ["Section A"]

    def test_split_by_size_short_text(self):
        text = "Short text"
        chunks = self.svc._split_by_size(text, ["S1"], page_starts_at=1)
        assert len(chunks) == 1
        assert chunks[0].text == "Short text"
        assert chunks[0].page_starts_at == 1

    def test_split_by_size_long_text(self):
        paragraphs = ["Paragraph " + str(i) + " word" * 40 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = self.svc._split_by_size(text, ["S1"])
        assert len(chunks) > 1

    def test_merge_small_chunks(self):
        small = [
            Chunk(text="a", metadata={}, chunk_index=0, section_path=["X"]),
            Chunk(text="b", metadata={}, chunk_index=1, section_path=["X"]),
        ]
        merged = self.svc._merge_small_chunks(small)
        assert len(merged) == 1
        assert "a" in merged[0].text
        assert "b" in merged[0].text

    def test_merge_small_chunks_empty(self):
        assert self.svc._merge_small_chunks([]) == []

    def test_merge_small_chunks_large_stays(self):
        large = [
            Chunk(text="x" * 200, metadata={}, chunk_index=0, section_path=["A"]),
            Chunk(text="y" * 200, metadata={}, chunk_index=1, section_path=["B"]),
        ]
        merged = self.svc._merge_small_chunks(large)
        assert len(merged) == 2

    def test_merge_small_chunks_different_sections(self):
        small = [
            Chunk(text="a", metadata={"section_path": ["X"]}, chunk_index=0, section_path=["X"]),
            Chunk(text="b", metadata={"section_path": ["Y"]}, chunk_index=1, section_path=["Y"]),
        ]
        merged = self.svc._merge_small_chunks(small)
        assert len(merged) == 1

    def test_add_overlap_single_chunk(self):
        chunks = [Chunk(text="only one", metadata={}, chunk_index=0)]
        result = self.svc._add_overlap(chunks)
        assert len(result) == 1
        assert result[0].text == "only one"

    def test_add_overlap_multiple_chunks(self):
        chunks = [
            Chunk(text="First chunk text", metadata={}, chunk_index=0),
            Chunk(text="Second chunk text here", metadata={}, chunk_index=1),
        ]
        result = self.svc._add_overlap(chunks)
        assert "..." in result[0].text
        assert "Second" in result[0].text
        assert result[1].text == "Second chunk text here"

    def test_page_starts_at_propagated(self):
        tree = {
            "heading": {"title": "Root"},
            "content": "",
            "children": [
                {
                    "heading": {"title": "S", "page_starts_at": 5},
                    "content": "some content",
                    "children": [],
                }
            ],
        }
        chunks = self.svc._traverse_tree(tree, [])
        assert chunks[0].page_starts_at == 5
