from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class OrderStatus(enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class User(Base):
    __tablename__ = "User"
    id = Column(Integer, primary_key=True, index=True)
    phoneNumber = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=True)
    name = Column(String(100))
    address = Column(String(255))
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    updatedAt = Column(DateTime(timezone=True), onupdate=func.now())
    
    orders = relationship("Order", back_populates="user")

class Category(Base):
    __tablename__ = "Category"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)
    description = Column(String(255))
    
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "Product"
    id = Column(Integer, primary_key=True, index=True)
    categoryId = Column(Integer, ForeignKey("Category.id")) # Foreign Key relationship
    name = Column(String(100))
    description = Column(Text)
    price = Column(Numeric(10, 2))
    stockQuantity = Column(Integer, default=0)
    imageUrl = Column(String(255))
    isActive = Column(Boolean, default=True)
    updatedAt = Column(DateTime(timezone=True), onupdate=func.now())
    
    category = relationship("Category", back_populates="products")
    images = relationship("ProductImage", back_populates="product")

class ProductImage(Base):
    __tablename__ = "ProductImage"
    id = Column(Integer, primary_key=True, index=True)
    productId = Column(Integer, ForeignKey("Product.id"))
    imageUrl = Column(String(255))
    isPrimary = Column(Boolean, default=False)
    
    product = relationship("Product", back_populates="images")

class Order(Base):
    __tablename__ = "Order"
    id = Column(Integer, primary_key=True, index=True)
    userId = Column(Integer, ForeignKey("User.id"))
    
    # Snapshot of customer details
    customerName = Column(String(100))
    customerEmail = Column(String(100))
    customerPhone = Column(String(50))
    
    shippingAddress = Column(Text)
    paymentMethod = Column(String(50))
    
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    totalAmount = Column(Numeric(10, 2))
    paymentRef = Column(String(100))
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    updatedAt = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "OrderItem"
    id = Column(Integer, primary_key=True, index=True)
    orderId = Column(Integer, ForeignKey("Order.id"))
    productId = Column(Integer, ForeignKey("Product.id"))
    quantity = Column(Integer)
    unitPrice = Column(Numeric(10, 2))

    order = relationship("Order", back_populates="items")
    # product relationship could be added
