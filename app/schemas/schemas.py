from pydantic import BaseModel, validator
from datetime import datetime


class ChatRequest(BaseModel):
    """Request schema for AI chat queries."""
    query: str
    user_id: str = "default_guest"


class OrderItemSchema(BaseModel):
    """Schema for individual order items."""
    product_id: int
    quantity: int


class OrderCreate(BaseModel):
    """Legacy schema for creating draft orders."""
    user_phone: str
    user_name: str
    user_email: str | None = None
    shipping_address: str
    payment_method: str
    items: list[OrderItemSchema]


class PlaceOrderRequest(BaseModel):
    """
    Request schema for placing a new order with transaction support.
    
    Validates:
    - Payment method must be 'Debit Card' or 'Cash on Delivery'
    - At least one item must be included
    """
    user_phone: str
    user_name: str
    user_email: str | None = None
    shipping_address: str
    payment_method: str
    items: list[OrderItemSchema]
    
    @validator('payment_method')
    def validate_payment_method(cls, v):
        valid_methods = ["Debit Card", "Cash on Delivery"]
        if v not in valid_methods:
            raise ValueError(f"Payment method must be one of: {', '.join(valid_methods)}")
        return v
    
    @validator('items')
    def validate_items(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Order must contain at least one item")
        return v


class PlaceOrderResponse(BaseModel):
    """Response schema for successful order placement."""
    order_id: int
    status: str
    total_amount: float
    payment_method: str
    message: str


class ProductCreate(BaseModel):
    """Schema for creating a new product."""
    name: str
    description: str | None = None
    price: float
    stockQuantity: int
    categoryId: int
    imageUrl: str | None = None
    isActive: bool = True


class ProductUpdate(BaseModel):
    """Schema for updating an existing product."""
    name: str | None = None
    description: str | None = None
    price: float | None = None
    stockQuantity: int | None = None
    categoryId: int | None = None
    imageUrl: str | None = None
    isActive: bool | None = None


class OrderStatusUpdate(BaseModel):
    """Schema for updating order status."""
    status: str


class BusinessSettingsBase(BaseModel):
    business_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    whatsapp_number: str | None = None
    address: str | None = None
    bank_details: str | None = None

class BusinessSettingsCreate(BusinessSettingsBase):
    pass

class BusinessSettingsUpdate(BusinessSettingsBase):
    pass

class BusinessSettingsResponse(BusinessSettingsBase):
    id: int
    updated_at: datetime | None = None

    class Config:
        from_attributes = True

