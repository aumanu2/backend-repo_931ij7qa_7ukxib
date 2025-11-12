"""
Database Schemas

Pydantic models that define MongoDB collections used by the app.
Each class name (lowercased) maps to a collection name.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

# Product collection
class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    image: Optional[str] = Field(None, description="Image URL")
    in_stock: bool = Field(True, description="Whether product is in stock")
    stock_qty: int = Field(50, ge=0, description="Units in stock")

# Order Item (embedded in Order)
class OrderItem(BaseModel):
    product_id: str = Field(..., description="Referenced product _id as string")
    title: str = Field(..., description="Snapshot of product title at purchase time")
    price: float = Field(..., ge=0, description="Unit price at purchase time")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    image: Optional[str] = None

# Order collection
class Order(BaseModel):
    customer_name: str = Field(..., description="Customer full name")
    customer_email: EmailStr = Field(..., description="Customer email")
    customer_address: str = Field(..., description="Shipping address")
    items: List[OrderItem] = Field(..., description="List of purchased items")
    subtotal: float = Field(..., ge=0)
    shipping: float = Field(0, ge=0)
    total: float = Field(..., ge=0)
    status: str = Field("processing", description="Order status")
