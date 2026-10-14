from typing import Any, Union
from pydantic import BaseModel, Field, field_validator


class RawOrder(BaseModel):
    id: int
    name: str = ""
    phone: Any = None
    email: str = ""
    amount: Union[int, float] = 0
    created_at: str = ""

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("amount", mode="before")
    @classmethod
    def sanitize_amount(cls, v: Any) -> Union[int, float]:
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return v
        try:
            val_float = float(v)
            if val_float.is_integer():
                return int(val_float)
            return val_float
        except (ValueError, TypeError):
            raise ValueError(f"Invalid numeric amount: {v}")


class ClientItem(BaseModel):
    name: str
    phone: str = Field(..., pattern=r"^\+7[3-9]\d{9}$", description="Normalized Russian phone starting with +7")
    email: str
    amount: Union[int, float]


class Stats(BaseModel):
    received: int = Field(..., description="Total number of raw input records")
    unique: int = Field(..., description="Number of retained unique clients")
    duplicates_merged: int = Field(..., description="Number of valid records removed as duplicates")
    invalid_dropped: int = Field(..., description="Number of records rejected by validation")


class OrdersResponse(BaseModel):
    clients: list[ClientItem]
    stats: Stats
