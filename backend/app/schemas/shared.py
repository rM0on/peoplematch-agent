from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


SchemaVersion = Literal["1.0"]
SyntheticDataOrigin = Literal["synthetic_sandbox"]


class ContractModel(BaseModel):
    """Strict base for versioned sandbox data contracts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Seniority(str, Enum):
    EARLY_CAREER = "early_career"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"


class RemotePolicy(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    FLEXIBLE = "flexible"


class ProductStage(str, Enum):
    ZERO_TO_ONE = "zero_to_one"
    GROWTH = "growth"
    MATURE = "mature"
