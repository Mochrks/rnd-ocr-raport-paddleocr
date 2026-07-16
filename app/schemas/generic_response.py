from pydantic import BaseModel
from typing import Any, Optional


class ErrorDetail(BaseModel):
    """Detail error response"""
    
    code: str
    message: str
    details: Optional[dict] = None


class GenericResponse(BaseModel):
    """Generic response untuk semua OCR endpoints"""
    
    status: str  # "success" atau "error"
    code: int  # HTTP status code
    message: str
    data: Optional[Any] = None
    accuracy_percentage: Optional[float] = None
    elapsed_time: Optional[float] = None
    raw_text: Optional[Any] = None
    error: Optional[ErrorDetail] = None


class SuccessResponse(GenericResponse):
    """Success response"""
    
    status: str = "success"
    error: Optional[ErrorDetail] = None
    

class ErrorResponse(GenericResponse):
    """Error response"""
    
    status: str = "error"
    data: Optional[Any] = None
