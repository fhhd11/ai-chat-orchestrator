"""Common models for API responses, pagination, and error handling"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


class PaginationInfo(BaseModel):
    """Pagination information"""
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    limit: int = Field(..., ge=1, le=100, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response wrapper"""
    success: bool = Field(True, description="Request success status")
    data: T = Field(..., description="Response data")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper"""
    success: bool = Field(True, description="Request success status")
    data: Dict[str, Any] = Field(..., description="Response data with items and pagination")
    
    def __init__(self, items: List[T], pagination: PaginationInfo, **kwargs):
        super().__init__(
            data={
                "items": items,
                "pagination": pagination.model_dump()
            },
            **kwargs
        )


class ErrorDetail(BaseModel):
    """Error detail information"""
    field: Optional[str] = Field(None, description="Field that caused the error")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = Field(False, description="Request success status")
    error: Dict[str, Any] = Field(..., description="Error information")
    
    @classmethod
    def create(
        cls,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_errors: Optional[List[ErrorDetail]] = None
    ) -> "ErrorResponse":
        """Create error response"""
        error_data = {
            "message": message,
            "code": code,
            "details": details or {},
        }
        
        if field_errors:
            error_data["field_errors"] = [error.model_dump() for error in field_errors]
            
        return cls(error=error_data)


class SearchFilters(BaseModel):
    """Common search and filtering parameters"""
    q: Optional[str] = Field(None, description="Search query", min_length=1, max_length=200)
    created_after: Optional[datetime] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date (before)")
    updated_after: Optional[datetime] = Field(None, description="Filter by update date (after)")
    updated_before: Optional[datetime] = Field(None, description="Filter by update date (before)")


class SortOrder(str):
    """Sort order enumeration"""
    ASC = "asc"
    DESC = "desc"


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(1, ge=1, description="Page number (1-based)")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field("created_at", description="Sort field")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")
    
    def get_offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.limit


class HealthStatus(BaseModel):
    """Health check status"""
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    response_time: Optional[float] = Field(None, description="Response time in seconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional status details")


class SystemInfo(BaseModel):
    """System information"""
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    debug: bool = Field(..., description="Debug mode status")
    uptime: float = Field(..., description="Uptime in seconds")
    features: Dict[str, bool] = Field(..., description="Available features")
    endpoints: Dict[str, Optional[str]] = Field(..., description="Available endpoints")