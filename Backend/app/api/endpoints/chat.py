from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.ai_agent import agent
from app.schemas.schemas import ChatRequest

router = APIRouter()

@router.post("/chat")
def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Chat with the AI agent.
    The AI can help with product information, prices, and availability.
    """
    try:
        response = agent.generate_response(request.query, db, request.user_id)
        return {"response": response}
    except Exception as e:
        print(f"Error in /chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
