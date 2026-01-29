# app/schemas/common.py

from pydantic import BaseModel
from typing import Any, Generic, TypeVar

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """Generic API response wrapper"""
    success: bool = True
    data: T
    message: str = "Operation successful"


class ErrorResponse(BaseModel):
    """Error response schema"""
    success: bool = False
    error: str
    detail: dict[str, Any] | None = None


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = 1
    limit: int = 20
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit
