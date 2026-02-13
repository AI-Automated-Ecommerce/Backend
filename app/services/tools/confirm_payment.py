from langchain_core.tools import tool

@tool
def confirm_user_payment(customer_phone: str, transaction_ref: str = None) -> str:
    """
    Confirm that the user has made a payment for their pending order.
    Use this tool when the user says they have paid, transferred the money, or sends a slip.
    This updates the order status to 'PAYMENT_REVIEW_REQUESTED' so the admin can verify it.
    
    Args:
        customer_phone: The customer's phone number.
        transaction_ref: (Optional) The transaction reference number or slip details if provided by the user.
    """
    print(f"DEBUG: TOOL confirm_user_payment called. Phone={customer_phone}, Ref={transaction_ref}")
    from app.core.database import SessionLocal
    from app.models.models import Order, OrderStatus
    
    db = SessionLocal()
    try:
        # Find the most recent PENDING order for this user
        order = db.query(Order).filter(
            Order.customerPhone == customer_phone,
            Order.status == OrderStatus.PENDING
        ).order_by(Order.createdAt.desc()).first()
        
        if not order:
            return "I couldn't find a pending order for your number. Please make sure you have generated an invoice first."
        
        # Update status
        order.status = OrderStatus.PAYMENT_REVIEW_REQUESTED
        if transaction_ref:
            order.paymentRef = transaction_ref
            
        db.commit()
        
        return (f"Thank you! I have marked your order #{order.id} as PAID/REVIEW REQUESTED.\n"
                f"Our team will verify the payment and ship your items soon.\n"
                f"You will receive a confirmation once verified.")
    except Exception as e:
        print(f"ERROR in confirm_user_payment: {e}")
        return "An error occurred while updating your payment status. Please try again or contact support."
    finally:
        db.close()
