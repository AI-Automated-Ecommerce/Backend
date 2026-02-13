import os
import httpx
import asyncio
from fastapi import APIRouter, Depends, Request, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.ai_agent import agent
from app.services.chat_history import add_message, clear_chat_history


router = APIRouter()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_verify_token_123")


@router.get("/whatsapp")
async def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    """
    Webhook verification endpoint.
    WhatsApp sends a GET request to verify the webhook URL.
    """
    print(f"🔐 Webhook verification request - Mode: {mode}, Token: {token}")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified successfully!")
        return int(challenge)
    else:
        print(f"❌ Verification failed - Expected token: {VERIFY_TOKEN}, Got: {token}")
        raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # ... (omitted webhook logic) ...
    try:
        data = await request.json()
        print(f"Received webhook data: {data}")
        
        # Check if it's a valid message object
        entry = data.get("entry", [])[0] if data.get("entry") else {}
        changes = entry.get("changes", [])[0] if entry.get("changes") else {}
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        # Extract the phone number ID that received the message
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")

        if not messages:
            print("No messages in payload (might be a status update)")
            return {"status": "ignored", "reason": "no messages"}

        msg_body = messages[0]
        from_number = msg_body.get("from")  # User's phone number
        msg_type = msg_body.get("type")
        message_id = msg_body.get("id")
        
        print(f"Message from: {from_number}, Type: {msg_type}, ID: {message_id}")

        # We only support text messages for now
        if msg_type == "text":
            user_message = msg_body["text"]["body"]
            print(f"User said: {user_message}")
            
            # Check for special commands
            if user_message.strip().lower() == "/clear":
                clear_chat_history(db, from_number)
                await send_reply(from_number, "Conversaton history cleared.", phone_number_id)
                # Also need to clear agent memory for this user
                agent.clear_history(from_number) 
                return {"status": "processed", "command": "clear"}

            # Save user message to database
            add_message(db, from_number, "user", user_message)
            
            # Process in background to avoid webhook timeout and implement human-like delay
            background_tasks.add_task(handle_whatsapp_response, from_number, user_message, db, phone_number_id, message_id)
        
        return {"status": "processed"}

    except Exception as e:
        print(f"Error in WhatsApp webhook: {e}")
        return {"status": "error", "message": str(e)}


async def handle_whatsapp_response(from_number: str, user_message: str, db: Session, phone_number_id: str = None, message_id: str = None):
    """
    Background task to process AI response and send message immediately.
    """
    try:
        # 0. Send typing indicator (and mark as read)
        await send_typing_indicator(from_number, phone_number_id, message_id)

        # 1. Generate AI response (do this first)
        response_data = agent.generate_response_with_images(user_message, db, from_number)
        ai_response = response_data["text"]
        images = response_data.get("images", [])
        
        # 2. No delay - send immediately
        
        # 4. Send product images first (if any)
        if images:
            image_tasks = []
            for img_data in images:
                caption = f"{img_data['product_name']} - ${img_data['price']:.2f}"
                if img_data['stock'] > 0:
                    caption += f" ({img_data['stock']} in stock)"
                else:
                    caption += " (Out of stock)"
                
                # Add to task list for parallel execution
                image_tasks.append(send_image(from_number, img_data['image_url'], caption, phone_number_id))
            
            # Execute all image sends in parallel
            if image_tasks:
                print(f"Sending {len(image_tasks)} images in parallel...")
                await asyncio.gather(*image_tasks)
        
        # 5. Send final text reply (one single message to reduce delay)
        if ai_response and ai_response.strip():
            # Send the full response immediately
            await send_reply(from_number, ai_response.strip(), phone_number_id)
            # Save AI response to database
            add_message(db, from_number, "assistant", ai_response.strip())
        
        print(f"Successfully processed and sent response immediately")

    except Exception as e:
        print(f"Error processing background response: {e}")


async def send_typing_indicator(to_number: str, phone_number_id: str = None, message_id: str = None):
    """
    Send a typing indicator to the user.
    Also marks the message as read if message_id is provided.
    """
    sender_id = phone_number_id or PHONE_NUMBER_ID
    
    if not WHATSAPP_TOKEN or not sender_id:
        return

    url = f"https://graph.facebook.com/v21.0/{sender_id}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Mark message as read (if we have ID)
        if message_id:
            payload_read = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }
            try:
                # Note: 'read' status is sent to a different endpoint usually? 
                # No, it's POST /messages for 'status' updates? 
                # Actually it is POST /{PHONE_NUMBER_ID}/messages for sending messages, 
                # BUT statuses are often:
                # POST /v21.0/{PHONE_NUMBER_ID}/messages
                # payload: { "messaging_product": "whatsapp", "status": "read", "message_id": "..." }
                # This IS correct for marking as read.
                res = await client.post(url, json=payload_read, headers=headers)
                print(f"👀 Marked message {message_id} as read: {res.status_code}")
            except Exception as e:
                print(f"⚠️ Failed to mark read: {e}")

        # 2. Send typing indicator (Best Effort)
        # This payload is for 'sender_action' which works on some tiers/integrations.
        # It's explicitly supported in on-premise, and often Cloud.
        payload_typing = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "sender_action", # This is the standard 'typing' payload key
            "sender_action": "typing_on" # or "typing_off"
        }
        
        # Note: If this 400s, it's not fatal.
        try:
             res = await client.post(url, json=payload_typing, headers=headers)
             # print(f"⌨️ Sent typing indicator: {res.status_code} - {res.text}")
             if res.status_code != 200:
                 # Fallback/Silence failure
                 pass
        except Exception as e:
            print(f"⚠️ Failed to send typing: {e}")



async def send_reply(to_number: str, text_body: str, phone_number_id: str = None):
    """
    Send a WhatsApp message using Meta Cloud API.
    """
    # Use the passed ID if available, otherwise fallback to env var
    sender_id = phone_number_id or PHONE_NUMBER_ID
    
    if not WHATSAPP_TOKEN or not sender_id:
        print("❌ Meta API Credentials missing (Token or Phone Number ID)")
        return

    url = f"https://graph.facebook.com/v21.0/{sender_id}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_body}
    }
    
    print(f"📤 Sending to {to_number} from {sender_id}: {text_body[:50]}...")
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers)
        print(f"📬 Meta API Response: {res.status_code} - {res.text}")
        if res.status_code not in [200, 201]:
            print(f"❌ Failed to send WhatsApp message: {res.text}")
        else:
            print(f"✅ Message sent successfully!")
    except Exception as e:
        print(f"❌ Error sending message: {e}")


async def send_image(to_number: str, image_url: str, caption: str = "", phone_number_id: str = None):
    """
    Send an image via WhatsApp using Meta Cloud API.
    The image will be displayed directly in the chat, not as a link.
    """
    # Use the passed ID if available, otherwise fallback to env var
    sender_id = phone_number_id or PHONE_NUMBER_ID

    if not WHATSAPP_TOKEN or not sender_id:
        print("❌ Meta API Credentials missing (Token or Phone Number ID)")
        return False

    url = f"https://graph.facebook.com/v21.0/{sender_id}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    
    print(f"🖼️ Sending image to {to_number} from {sender_id}: {image_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers)
        print(f"📬 Meta API Response: {res.status_code} - {res.text}")
        if res.status_code not in [200, 201]:
            print(f"❌ Failed to send image: {res.text}")
            return False
        else:
            print(f"✅ Image sent successfully!")
            return True
    except Exception as e:
        print(f"❌ Error sending image: {e}")
        return False

