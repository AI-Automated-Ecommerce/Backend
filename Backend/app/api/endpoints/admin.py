from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Order, Product, User
from app.schemas.schemas import OrderStatusUpdate
from app.services.google_drive import upload_to_drive

router = APIRouter()

@router.get("/admin/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_orders = db.query(Order).count()
    pending_orders = db.query(Order).filter(Order.status == "PENDING").count()
    total_revenue = db.query(func.sum(Order.totalAmount)).scalar() or 0
    total_products = db.query(Product).count()
    total_customers = db.query(User).count()
    
    return {
        "totalOrders": total_orders,
        "pendingOrders": pending_orders,
        "totalRevenue": float(total_revenue),
        "totalProducts": total_products,
        "totalCustomers": total_customers
    }

@router.get("/admin/orders")
def get_admin_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.createdAt.desc()).all()
    # Serialize with customer info
    result = []
    for o in orders:
        result.append({
            "id": str(o.id),
            "customerName": o.customerName or o.user.name,
            "customerEmail": o.customerEmail or f"user{o.user.id}@example.com",
            "customerPhone": o.customerPhone or o.user.phoneNumber,
            "shippingAddress": o.shippingAddress or o.user.address,
            "paymentMethod": o.paymentMethod or "N/A",
            "total": float(o.totalAmount),
            "status": o.status.value.lower() if hasattr(o.status, 'value') else o.status.lower(),
            "createdAt": o.createdAt,
            "items": [
                {
                    "productId": str(i.productId),
                    "productName": db.query(Product.name).filter(Product.id == i.productId).scalar() or "Unknown",
                    "quantity": i.quantity,
                    "price": float(i.unitPrice)
                } for i in o.items
            ]
        })
    return result

@router.put("/admin/orders/{order_id}/status")
def update_order_status(order_id: int, status_update: OrderStatusUpdate, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Map string status to Enum if needed, or just partial match
    # Assuming simplistic status for now
    valid_statuses = ["PENDING", "PAID", "SHIPPED", "COMPLETED", "CANCELLED"]
    new_status = status_update.status.upper()
    if new_status not in valid_statuses:
         raise HTTPException(status_code=400, detail="Invalid status")
         
    order.status = new_status
    db.commit()
    return {"status": "success", "new_status": new_status}

@router.get("/admin/customers")
def get_customers(db: Session = Depends(get_db)):
    users = db.query(User).all()
    result = []
    for u in users:
        order_count = len(u.orders)
        total_spent = sum(o.totalAmount for o in u.orders)
        result.append({
            "id": str(u.id),
            "name": u.name,
            "email": f"user{u.id}@example.com", # Placeholder
            "phone": u.phoneNumber,
            "address": u.address or "N/A",
            "totalOrders": order_count,
            "totalSpent": float(total_spent),
            "createdAt": u.createdAt
        })
    return result

@router.get("/admin/products")
def get_admin_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    result = []
    for p in products:
        result.append({
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "price": float(p.price),
            "stockQuantity": p.stockQuantity,
            "category": p.category.name if p.category else "Uncategorized",
            "categoryId": p.categoryId,
            "imageUrl": p.imageUrl,
            "isActive": p.isActive
        })
    return result

@router.post("/admin/upload")
async def upload_image(file: UploadFile = File(...)):
    try:
        content = await file.read()
        image_url = upload_to_drive(content, file.filename, file.content_type)
        return {"imageUrl": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
