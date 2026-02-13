from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db
from app.models.models import Order, OrderItem, User, Product, OrderStatus
from app.schemas.schemas import OrderCreate, PlaceOrderRequest, PlaceOrderResponse, PaymentReceiptUpload
from app.services.google_drive import upload_to_drive

router = APIRouter()


@router.post("/orders/place", response_model=PlaceOrderResponse)
def place_order(order_data: PlaceOrderRequest, db: Session = Depends(get_db)):
    """
    Place a new order with full transactional support.
    
    This endpoint provides ACID transaction guarantees:
    - Validates payment method (Debit Card or Cash on Delivery)
    - Checks product availability and stock levels
    - Creates order with all items
    - Reduces inventory atomically
    - Automatically rolls back on any error
    
    Args:
        order_data: Order details including customer info, items, and payment method
        db: Database session
        
    Returns:
        PlaceOrderResponse with order ID, status, total amount, and confirmation message
        
    Raises:
        HTTPException 404: Product not found or inactive
        HTTPException 400: Insufficient stock
        HTTPException 422: Invalid payment method (handled by Pydantic)
        HTTPException 500: Database or unexpected errors
    """
    try:
        # Step 1: Validate all products exist and have sufficient stock
        items_to_process = []
        total_amount = 0.0
        
        for item in order_data.items:
            product = db.query(Product).filter(
                Product.id == item.product_id,
                Product.isActive == True
            ).first()
            
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product with ID {item.product_id} not found or inactive"
                )
            
            if product.stockQuantity < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {product.name}. Available: {product.stockQuantity}, Requested: {item.quantity}"
                )
            
            item_total = float(product.price) * item.quantity
            total_amount += item_total
            
            items_to_process.append({
                'product': product,
                'quantity': item.quantity,
                'unit_price': product.price
            })
        
        # 2. Find or create user
        user = db.query(User).filter(User.phoneNumber == order_data.user_phone).first()
        if not user:
            user = User(
                phoneNumber=order_data.user_phone,
                name=order_data.user_name,
                email=order_data.user_email,
                address=order_data.shipping_address
            )
            db.add(user)
            db.flush()  # Get user ID without committing
        else:
            # Update user details if provided
            if order_data.user_name:
                user.name = order_data.user_name
            if order_data.shipping_address:
                user.address = order_data.shipping_address
            if order_data.user_email and not user.email:
                user.email = order_data.user_email
        
        # 3. Create order
        new_order = Order(
            userId=user.id,
            status="PENDING",
            totalAmount=total_amount,
            customerName=order_data.user_name,
            customerEmail=order_data.user_email,
            customerPhone=order_data.user_phone,
            shippingAddress=order_data.shipping_address,
            paymentMethod=order_data.payment_method
        )
        db.add(new_order)
        db.flush()  # Get order ID without committing
        
        # 4. Create order items and reduce inventory (transactional)
        for item_data in items_to_process:
            product = item_data['product']
            quantity = item_data['quantity']
            
            # Create order item
            order_item = OrderItem(
                orderId=new_order.id,
                productId=product.id,
                quantity=quantity,
                unitPrice=item_data['unit_price']
            )
            db.add(order_item)
            
            # Reduce inventory
            product.stockQuantity -= quantity
        
        # 5. Commit transaction
        db.commit()
        db.refresh(new_order)
        
        return PlaceOrderResponse(
            order_id=new_order.id,
            status="PENDING",
            total_amount=total_amount,
            payment_method=order_data.payment_method,
            message=f"Order placed successfully. Total: ${total_amount:.2f}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        db.rollback()
        raise
    except SQLAlchemyError as e:
        # Database errors
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred while placing order: {str(e)}"
        )
    except Exception as e:
        # Any other errors
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post("/orders/initiate")
def create_draft_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """
    Create a new order with detailed user and shipping info.
    """
    # 1. Find or create user
    user = db.query(User).filter(User.phoneNumber == order_data.user_phone).first()
    if not user:
        user = User(
            phoneNumber=order_data.user_phone, 
            name=order_data.user_name,
            email=order_data.user_email,
            address=order_data.shipping_address
        )
        db.add(user)
    else:
        # Update user details if provided and missing/different? 
        # For simple logic, let's update address and name if they are "Guest" or empty
        if order_data.user_name:
            user.name = order_data.user_name
        if order_data.shipping_address:
            user.address = order_data.shipping_address
        if order_data.user_email and not user.email:
            user.email = order_data.user_email
            
    db.commit()
    db.refresh(user)

    # 2. Create Order
    new_order = Order(
        userId=user.id, 
        status="PENDING", 
        totalAmount=0,
        customerName=order_data.user_name,
        customerEmail=order_data.user_email,
        customerPhone=order_data.user_phone,
        shippingAddress=order_data.shipping_address,
        paymentMethod=order_data.payment_method
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # 3. Add Items & Calculate Total
    total = 0.0
    for item in order_data.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
             qty = item.quantity
             price = float(product.price)
             total += price * qty
             
             order_item = OrderItem(
                 orderId=new_order.id, 
                 productId=product.id, 
                 quantity=qty, 
                 unitPrice=product.price
             )
             db.add(order_item)
    
    # 4. Update Order Total
    new_order.totalAmount = total
    db.commit()
    
    # 5. Return Checkout URL
    # Assuming frontend runs on localhost:3000
    checkout_url = f"http://localhost:3000/checkout/{new_order.id}"
    return {
        "status": "created", 
        "order_id": new_order.id, 
        "total": total,
        "checkout_url": checkout_url
    }


@router.post("/orders/{order_id}/payment-receipt", response_model=PaymentReceiptUpload)
async def upload_payment_receipt(
    order_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Upload payment receipt for an order.
    
    This endpoint:
    - Accepts image uploads for payment proof
    - Uploads to Google Drive for storage
    - Updates order status to PAYMENT_REVIEW_REQUESTED
    - Stores receipt URL in the order record
    
    Args:
        order_id: ID of the order
        file: Payment receipt image file
        db: Database session
        
    Returns:
        PaymentReceiptUpload with order ID, receipt URL, status, and message
        
    Raises:
        HTTPException 404: Order not found
        HTTPException 400: Invalid file or upload error
        HTTPException 500: Database or unexpected errors
    """
    try:
        # Validate order exists
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        
        # Validate file type (accept common image formats)
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            )
        
        # Read file content
        content = await file.read()
        
        # Upload to Google Drive
        receipt_url = upload_to_drive(content, file.filename, file.content_type)
        
        # Update order with receipt URL and status
        order.paymentReceiptUrl = receipt_url
        order.status = OrderStatus.PAYMENT_REVIEW_REQUESTED
        
        db.commit()
        db.refresh(order)
        
        return PaymentReceiptUpload(
            order_id=order.id,
            receipt_url=receipt_url,
            status="PAYMENT_REVIEW_REQUESTED",
            message=f"Payment receipt uploaded successfully. Order status updated to payment review."
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload payment receipt: {str(e)}"
        )

