from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.models import Order, Product, User, Message, OrderStatus
from app.schemas.schemas import OrderStatusUpdate


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
    from sqlalchemy.orm import joinedload
    orders = db.query(Order).options(joinedload(Order.user), joinedload(Order.items)).order_by(Order.createdAt.desc()).all()
    # Serialize with customer info
    result = []
    for o in orders:
        customer_name = "Unknown"
        customer_email = "N/A"
        customer_phone = "N/A"
        shipping_address = "N/A"

        # Check if user exists before accessing attributes
        if o.user:
            customer_name = o.user.name or "Unknown"
            # specific fix for the crash: check if o.user.id exists/is not None just in case, though logically it should be if o.user is not None
            user_id = o.user.id if o.user.id else "unknown"
            customer_email = f"user{user_id}@example.com"
            customer_phone = o.user.phoneNumber or "N/A"
            shipping_address = o.user.address or "N/A"
        
        # Override with order specific details if available
        if o.customerName:
            customer_name = o.customerName
        if o.customerEmail:
            customer_email = o.customerEmail
        if o.customerPhone:
            customer_phone = o.customerPhone
        if o.shippingAddress:
            shipping_address = o.shippingAddress

        result.append({
            "id": str(o.id),
            "customerName": customer_name,
            "customerEmail": customer_email,
            "customerPhone": customer_phone,
            "shippingAddress": shipping_address,
            "paymentMethod": o.paymentMethod or "N/A",
            "total": float(o.totalAmount) if o.totalAmount else 0.0,
            "status": o.status.value.lower() if hasattr(o.status, 'value') else str(o.status).lower(),
            "createdAt": o.createdAt,
            "items": [
                {
                    "productId": str(i.productId),
                    "productName": db.query(Product.name).filter(Product.id == i.productId).scalar() or "Unknown",
                    "quantity": i.quantity,
                    "price": float(i.unitPrice) if i.unitPrice else 0.0
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
    valid_statuses = ["PENDING", "PAYMENT_REVIEW_REQUESTED", "PAID", "SHIPPED", "COMPLETED", "CANCELLED"]
    new_status = status_update.status.upper()
    if new_status not in valid_statuses:
         raise HTTPException(status_code=400, detail="Invalid status")
    
    # Store old status to check for transitions
    old_status = order.status.value if hasattr(order.status, 'value') else str(order.status)
    
    # Update order status
    order.status = new_status
    db.commit()
    
    # Send WhatsApp notification when payment is confirmed
    if new_status == "PAID" and old_status == "PAYMENT_REVIEW_REQUESTED":
        try:
            from app.api.endpoints.whatsapp import send_reply
            
            customer_phone = order.customerPhone
            if customer_phone:
                message = (
                    "✅ *Payment Confirmed!*\n\n"
                    "Your payment has been successfully received and verified.\n\n"
                    "🚚 *Delivery Information:*\n"
                    "Your order will be delivered within *3-4 business days*.\n\n"
                    f"📦 *Order ID:* {order.id}\n"
                    f"💰 *Total Amount:* ${float(order.totalAmount):.2f}\n\n"
                    "Thank you for your purchase! 🎉"
                )
                send_reply(customer_phone, message)
                print(f"✅ WhatsApp payment confirmation sent to {customer_phone}")
        except Exception as e:
            print(f"⚠️ Failed to send WhatsApp notification: {e}")
            # Don't fail the status update if WhatsApp fails
    
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
        from app.services.cloudinary_service import upload_to_cloudinary
        content = await file.read()
        # Cloudinary uploader.upload can take a file-like object or bytes
        # However, the cloudinary_service function expects bytes based on current implementation
        # Or even better, we pass the bytes directly.
        image_url = upload_to_cloudinary(content, file.filename)
        return {"imageUrl": image_url}
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/chats")
def get_customer_chats(db: Session = Depends(get_db)):
    """
    Get all customer conversations with their latest message and ongoing orders.
    """
    from sqlalchemy.orm import joinedload
    from sqlalchemy import and_
    
    # Get all unique phone numbers that have sent messages
    unique_phones = db.query(Message.user_phone).distinct().all()
    phone_numbers = [phone[0] for phone in unique_phones]
    
    conversations = []
    
    for phone in phone_numbers:
        # Get user info if exists
        user = db.query(User).filter(User.phoneNumber == phone).first()
        customer_name = user.name if user else f"Customer {phone[-4:]}"
        
        # Get latest message
        latest_message = db.query(Message).filter(
            Message.user_phone == phone
        ).order_by(desc(Message.timestamp)).first()
        
        # Get message count
        message_count = db.query(Message).filter(Message.user_phone == phone).count()
        
        # Get ongoing orders (not completed or cancelled)
        ongoing_orders = db.query(Order).filter(
            and_(
                Order.customerPhone == phone,
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PAYMENT_REVIEW_REQUESTED, OrderStatus.PAID, OrderStatus.SHIPPED])
            )
        ).all()
        
        conversations.append({
            "phoneNumber": phone,
            "customerName": customer_name,
            "customerEmail": user.email if user and user.email else f"user{user.id}@example.com" if user else "N/A",
            "lastMessage": latest_message.content if latest_message else "No messages",
            "lastMessageTime": latest_message.timestamp if latest_message else None,
            "lastMessageRole": latest_message.role if latest_message else None,
            "messageCount": message_count,
            "ongoingOrders": [
                {
                    "id": str(order.id),
                    "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                    "totalAmount": float(order.totalAmount) if order.totalAmount else 0.0,
                    "createdAt": order.createdAt
                } for order in ongoing_orders
            ],
            "hasUnread": latest_message.role == "user" if latest_message else False
        })
    
    # Sort by last message time (most recent first)
    conversations.sort(key=lambda x: x["lastMessageTime"] or "", reverse=True)
    
    return conversations


@router.get("/admin/chats/{phone_number}")
def get_customer_chat_history(phone_number: str, db: Session = Depends(get_db)):
    """
    Get full chat history for a specific customer phone number.
    """
    # Get user info
    user = db.query(User).filter(User.phoneNumber == phone_number).first()
    
    # Get all messages for this phone number
    messages = db.query(Message).filter(
        Message.user_phone == phone_number
    ).order_by(Message.timestamp.asc()).all()
    
    # Get all orders for this customer
    orders = db.query(Order).options(joinedload(Order.items)).filter(
        Order.customerPhone == phone_number
    ).order_by(desc(Order.createdAt)).all()
    
    return {
        "phoneNumber": phone_number,
        "customerName": user.name if user else f"Customer {phone_number[-4:]}",
        "customerEmail": user.email if user and user.email else f"user{user.id}@example.com" if user else "N/A",
        "customerAddress": user.address if user else "N/A",
        "joinedDate": user.createdAt if user else None,
        "messages": [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            } for msg in messages
        ],
        "orders": [
            {
                "id": str(order.id),
                "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                "totalAmount": float(order.totalAmount) if order.totalAmount else 0.0,
                "createdAt": order.createdAt,
                "itemCount": len(order.items) if order.items else 0,
                "paymentMethod": order.paymentMethod or "N/A"
            } for order in orders
        ]
    }


@router.post("/admin/chats/{phone_number}/send")
def send_admin_message(phone_number: str, message_data: dict, db: Session = Depends(get_db)):
    """
    Send a message from admin to customer via WhatsApp.
    """
    try:
        from app.api.endpoints.whatsapp import send_reply
        
        message_content = message_data.get("message", "").strip()
        if not message_content:
            raise HTTPException(status_code=400, detail="Message content is required")
        
        # Send WhatsApp message
        send_reply(phone_number, message_content)
        
        # Save message to chat history
        new_message = Message(
            user_phone=phone_number,
            role="assistant",
            content=message_content
        )
        db.add(new_message)
        db.commit()
        
        return {"status": "success", "message": "Message sent successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
