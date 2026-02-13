from sqlalchemy.orm import Session
from app.models.models import Message
from typing import List

def add_message(db: Session, user_phone: str, role: str, content: str):
    """
    Save a message to the database.
    """
    if not content or not content.strip():
        return None
        
    new_message = Message(
        user_phone=user_phone,
        role=role,
        content=content
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message

def get_chat_history(db: Session, user_phone: str, limit: int = 10) -> List[Message]:
    """
    Retrieve recent chat history for a user.
    """
    return db.query(Message)\
        .filter(Message.user_phone == user_phone)\
        .order_by(Message.timestamp.desc())\
        .limit(limit)\
        .all()[::-1] # Reverse to get chronological order (oldest to newest)

def clear_chat_history(db: Session, user_phone: str):
    """
    Clear all chat history for a user.
    """
    db.query(Message).filter(Message.user_phone == user_phone).delete()
    db.commit()
