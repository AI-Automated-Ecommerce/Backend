from langchain_core.tools import tool


@tool
def get_payment_details(customer_phone: str) -> str:
    """
    Get the bank payment details for the business.
    Use this tool ONLY after the user has confirmed the invoice and is ready to pay.
    This also clears the user's cart.
    
    Args:
        customer_phone: The customer's phone number.
    """
    print("DEBUG: TOOL get_payment_details called")
    from app.core.database import SessionLocal
    from app.models.models import Cart, BusinessSettings
    
    db = SessionLocal()
    try:
        settings = db.query(BusinessSettings).first()
        if not settings or not settings.bank_details:
            return "Bank details are not currently configured. Please contact support."
        
        # Clear Cart (cascade will delete CartItems automatically)
        cart = db.query(Cart).filter(Cart.user_phone == customer_phone).first()
        if cart:
            db.delete(cart)
            db.commit()
        
        return f"Please transfer the amount to the following bank account:\n\n{settings.bank_details}\n\nOnce paid, please send a slip/screenshot here for manual verification."
    finally:
        db.close()
