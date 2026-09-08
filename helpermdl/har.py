from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class RequestData(BaseModel):
    headers: Optional[dict] = None
    body: Optional[Any] = None
    timestamp: Optional[str] = None


class ResponseData(BaseModel):
    status: int
    body: Optional[Any] = None
    headers: Optional[dict] = None
    timestamp: Optional[str] = None


class Params(BaseModel):
    method: str
    requests_count: int = 0
    request: Optional[RequestData] = None
    response: Optional[ResponseData] = None


class Endpoint(BaseModel):
    params: Dict[str, Params] = Field(default_factory=dict)


class HarToEndpoints(BaseModel):
    url: Dict[str, Dict[str, Dict[str, Endpoint]]] = Field(default_factory=dict)