from langchain_core.tools import tool

@tool
def get_business_details_tool() -> str:
    """
    Get detailed information about the business such as services, pricing, company history, etc.
    Use this tool when the user asks specific questions about what the business offers, its story, or pricing tiers.
    """
    print("DEBUG: TOOL get_business_details_tool called")
    from app.core.database import SessionLocal
    from app.models.models import BusinessDetail
    
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
