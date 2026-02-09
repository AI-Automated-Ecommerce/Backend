import os
import requests
import time
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.ai_agent import agent

router = APIRouter()

# Meta WhatsApp Configuration
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_API_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "my_secure_token")

@router.get("/whatsapp")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """
    Verification endpoint for Meta WhatsApp Webhook.
    """
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook for WhatsApp messages via Meta Cloud API.
    Handles incoming JSON payload.
    """
    try:
        data = await request.json()
        print(f"📩 Received webhook data: {data}")
        
        # Check if it's a valid message object
        entry = data.get("entry", [])[0] if data.get("entry") else {}
        changes = entry.get("changes", [])[0] if entry.get("changes") else {}
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            print("⚠️ No messages in payload (might be a status update)")
            return {"status": "ignored", "reason": "no messages"}

        msg_body = messages[0]
        from_number = msg_body.get("from")  # User's phone number
        msg_type = msg_body.get("type")
        
        print(f"📱 Message from: {from_number}, Type: {msg_type}")

        # We only support text messages for now
        if msg_type == "text":
            user_message = msg_body["text"]["body"]
            print(f"💬 User said: {user_message}")
            
            # Generate AI response with images
            response_data = agent.generate_response_with_images(user_message, db, from_number)
            ai_response = response_data["text"]
            images = response_data.get("images", [])
            
            print(f"🤖 AI response: {ai_response[:100]}...")
            print(f"🖼️ Found {len(images)} images to send")
            
            # Send product images first (if any)
            if images:
                print(f"📸 Attempting to send {len(images)} images...")
                for i, img_data in enumerate(images):
                    print(f"  Image {i+1}: {img_data['product_name']} - {img_data['image_url']}")
                    caption = f"📦 {img_data['product_name']} - ${img_data['price']:.2f}"
                    if img_data['stock'] > 0:
                        caption += f" ({img_data['stock']} in stock)"
                    else:
                        caption += " (Out of stock)"
                    
                    success = send_image(from_number, img_data['image_url'], caption)
                    print(f"  → Image {i+1} send result: {success}")
                    time.sleep(0.5)  # Small delay between images
                
                # Delay before sending text to avoid rate limiting
                time.sleep(1)
            else:
                print("⚠️ No images to send")
            
            # Then send the text reply
            send_reply(from_number, ai_response)
        
        return {"status": "processed"}

    except Exception as e:
        print(f"❌ Error in WhatsApp webhook: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


def send_reply(to_number: str, text_body: str):
    """
    Send a WhatsApp message using Meta Cloud API.
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("❌ Meta API Credentials missing in .env")
        return

    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
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
    
    print(f"📤 Sending to {to_number}: {text_body[:50]}...")
    
    try:
        res = requests.post(url, json=payload, headers=headers)
        print(f"📬 Meta API Response: {res.status_code} - {res.text}")
        if res.status_code not in [200, 201]:
            print(f"❌ Failed to send WhatsApp message: {res.text}")
        else:
            print(f"✅ Message sent successfully!")
    except Exception as e:
        print(f"❌ Error sending message: {e}")


def send_image(to_number: str, image_url: str, caption: str = ""):
    """
    Send an image via WhatsApp using Meta Cloud API.
    The image will be displayed directly in the chat, not as a link.
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("❌ Meta API Credentials missing in .env")
        return False

    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
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
    
    print(f"🖼️ Sending image to {to_number}: {image_url}")
    
    try:
        res = requests.post(url, json=payload, headers=headers)
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

