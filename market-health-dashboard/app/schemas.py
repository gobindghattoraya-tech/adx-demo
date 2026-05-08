"""
Pydantic response schemas — type safety and auto-docs.
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class HelloResponse(BaseModel):
    message: str
