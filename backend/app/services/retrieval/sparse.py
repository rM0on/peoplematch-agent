from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from app.schemas.retrieval import ChannelResult


TOKEN_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


@dataclass(frozen=True)
class BM25Document:
    entity_id: str
    text: str


class BM25Retriever:
    def __init__(
        self,
        documents: Sequence[BM25Document],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        ordered = sorted(documents, key=lambda item: item.entity_id)
        self._documents = ordered
        self._tokens = {item.entity_id: tokenize(item.text) for item in ordered}
        self._average_length = (
            sum(len(tokens) for tokens in self._tokens.values()) / len(ordered)
            if ordered
            else 0.0
        )
        self._document_frequency: Counter[str] = Counter()
        for tokens in self._tokens.values():
            self._document_frequency.update(set(tokens))

    def search(self, query: str, *, limit: int) -> list[ChannelResult]:
        query_tokens = tokenize(query)
        if not query_tokens or not self._documents or limit <= 0:
            return []
        corpus_size = len(self._documents)
        scores: list[tuple[str, float]] = []
        for document in self._documents:
            tokens = self._tokens[document.entity_id]
            frequencies = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                frequency = frequencies[token]
                document_frequency = self._document_frequency[token]
                if frequency == 0 or document_frequency == 0:
                    continue
                inverse_document_frequency = math.log(
                    1
                    + (corpus_size - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                length_ratio = (
                    len(tokens) / self._average_length if self._average_length else 0.0
                )
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length_ratio
                )
                score += inverse_document_frequency * (
                    frequency * (self.k1 + 1) / denominator
                )
            if score > 0:
                scores.append((document.entity_id, score))
        scores.sort(key=lambda item: (-item[1], item[0]))
        return [
            ChannelResult(entity_id=entity_id, rank=rank, score=score)
            for rank, (entity_id, score) in enumerate(scores[:limit], start=1)
        ]
