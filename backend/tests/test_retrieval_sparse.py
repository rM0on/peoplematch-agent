from __future__ import annotations


def test_tokenizer_is_unicode_safe_lowercase_and_deterministic() -> None:
    from app.services.retrieval.sparse import tokenize

    expected = ["python", "检索", "rank", "2026"]
    assert tokenize("Python，检索 / RANK-2026") == expected
    assert tokenize("Python，检索 / RANK-2026") == expected


def test_bm25_returns_expected_lexical_winner_and_empty_query() -> None:
    from app.services.retrieval.sparse import BM25Document, BM25Retriever

    retriever = BM25Retriever(
        [
            BM25Document(entity_id="b", text="vector database platform"),
            BM25Document(entity_id="a", text="candidate retrieval ranking evaluation"),
            BM25Document(entity_id="c", text="frontend interaction design"),
        ]
    )

    results = retriever.search("retrieval ranking", limit=3)
    assert results[0].entity_id == "a"
    assert results[0].score > 0
    assert retriever.search("", limit=3) == []
    assert retriever.search("unseen", limit=3) == []


def test_bm25_is_corpus_order_independent_and_ties_use_entity_id() -> None:
    from app.services.retrieval.sparse import BM25Document, BM25Retriever

    documents = [
        BM25Document(entity_id="z", text="shared token"),
        BM25Document(entity_id="a", text="shared token"),
        BM25Document(entity_id="m", text="different"),
    ]
    forward = BM25Retriever(documents).search("shared", limit=3)
    reverse = BM25Retriever(list(reversed(documents))).search("shared", limit=3)

    assert [item.entity_id for item in forward] == ["a", "z"]
    assert forward == reverse
    assert [item.rank for item in forward] == [1, 2]
