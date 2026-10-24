from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import OrderStatus


class ProductCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Mobile Phone", "price": 15000, "stock": 10}}
    )

    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    stock: int


class OrderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"product_id": 1, "quantity": 1}}
    )

    product_id: int
    quantity: int = Field(gt=0)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    total_price: float
    status: OrderStatus
    created_at: datetime