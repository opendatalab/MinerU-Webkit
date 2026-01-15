from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    code: int = 200
    message: str = "OK"
    data: T | None = None

    class Config:
        extra = "allow"  # 允许额外字段
