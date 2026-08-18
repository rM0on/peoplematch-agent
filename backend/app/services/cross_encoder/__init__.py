"""Frozen pretrained Cross-Encoder reranking services."""

from app.services.cross_encoder.contract import (
    MODEL_ID,
    MODEL_REVISION,
    TEXT_CONTRACT_FINGERPRINT,
    TEXT_SCHEMA_VERSION,
)

__all__ = [
    "MODEL_ID",
    "MODEL_REVISION",
    "TEXT_CONTRACT_FINGERPRINT",
    "TEXT_SCHEMA_VERSION",
]
