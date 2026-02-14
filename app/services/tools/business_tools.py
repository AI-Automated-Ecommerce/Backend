from langchain_core.tools import tool
from app.core.database import SessionLocal
from app.models.models import BusinessSettings, BusinessDetail

@tool
def get_business_info() -> str:
    """
    Get contact details and general information about the business.
    Use this tool when the user asks for contact info, address, email, or about the company.
    """
    print("DEBUG: TOOL get_business_info called")
    
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

@tool
def get_business_details_tool() -> str:
    """
    Get detailed information about the business such as services, pricing, company history, etc.
    Use this tool when the user asks specific questions about what the business offers, its story, or pricing tiers.
    """
    print("DEBUG: TOOL get_business_details_tool called")
    
    db = SessionLocal()
    try:
        details = db.query(BusinessDetail).all()
        if not details:
            return "No specific business details are currently configured."
        
        info_parts = []
        for detail in details:
            info_parts.append(f"--- {detail.title} ---\n{detail.content}")
            
        result = "\n\n".join(info_parts)
        print(f"DEBUG: TOOL get_business_details_tool returning: {result[:100]}...")
        return result
    finally:
        db.close()
