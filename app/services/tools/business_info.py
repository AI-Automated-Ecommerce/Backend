from langchain_core.tools import tool


@tool
def get_business_info() -> str:
    """
    Get contact details and general information about the business.
    Use this tool when the user asks for contact info, address, email, or about the company.
    """
    print("DEBUG: TOOL get_business_info called")
    from app.core.database import SessionLocal
    from app.models.models import BusinessSettings
    
    db = SessionLocal()
    try:
        settings = db.query(BusinessSettings).first()
        if not settings:
            return "Business information is not configured."
        
        info = f"Business Name: {settings.business_name}\n"
        if settings.contact_phone: info += f"Phone: {settings.contact_phone}\n"
        if settings.whatsapp_number: info += f"WhatsApp: {settings.whatsapp_number}\n"
        if settings.contact_email: info += f"Email: {settings.contact_email}\n"
        if settings.address: info += f"Address: {settings.address}\n"
        
        print(f"DEBUG: TOOL get_business_info returning: {info[:100]}...")
        return info
    finally:
        db.close()
