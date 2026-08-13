from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ApiResponse(BaseModel, Generic[DataT]):
    success: bool
    data: Optional[DataT] = None
    error: Optional[ApiError] = None
    request_id: str


class PaginatedData(BaseModel, Generic[DataT]):
    items: List[DataT]
    total: int
    limit: int
    offset: int
