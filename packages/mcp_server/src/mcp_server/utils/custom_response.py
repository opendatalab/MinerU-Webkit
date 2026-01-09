from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    code: int = 200
    message: str = "OK"
    data: Optional[T] = None

    class Config:
        extra = "allow"  # 允许额外字段
