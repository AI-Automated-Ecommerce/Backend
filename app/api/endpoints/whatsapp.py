from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.ai_agent import agent
from twilio.twiml.messaging_response import MessagingResponse

router = APIRouter()

@router.post("/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Webhook for WhatsApp messages via Twilio.
    'Body' is the user message, 'From' is the user's phone number.
    """
    try:
        # Generate AI response (using phone number as user_id for context)
        ai_response = agent.generate_response(Body, db, From)
        
        # Create Twilio XML response
        twiml_res = MessagingResponse()
        twiml_res.message(ai_response)
        
        return Response(content=str(twiml_res), media_type="application/xml")
    except Exception as e:
        print(f"Error in WhatsApp webhook: {e}")
        twiml_res = MessagingResponse()
        twiml_res.message("Sorry, I'm having trouble processing your request right now.")
        return Response(content=str(twiml_res), media_type="application/xml")
