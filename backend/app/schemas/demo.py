from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel


class DemoSamplesData(ContractModel):
    data_origin: Literal["synthetic_sandbox"] = "synthetic_sandbox"
    candidate_text: Annotated[
        str, StringConstraints(strip_whitespace=False, min_length=40, max_length=5000)
    ]
    job_text: Annotated[
        str, StringConstraints(strip_whitespace=False, min_length=60, max_length=6000)
    ]


class DemoIndexRebuildRequest(ContractModel):
    confirm: Literal[True]


class DemoIndexRebuildData(ContractModel):
    document_version: Literal["retrieval_doc_v4"]
    candidate_collection: str = Field(min_length=1, max_length=120)
    job_collection: str = Field(min_length=1, max_length=120)
    candidate_count: int = Field(ge=0)
    job_count: int = Field(ge=0)


__all__ = ["DemoIndexRebuildData", "DemoIndexRebuildRequest", "DemoSamplesData"]
