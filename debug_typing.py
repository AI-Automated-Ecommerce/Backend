import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path="/Users/yasiru/Documents/GitHub/AI-Automated-Business/Backend/.env")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Replace with the user's phone number you want to test with (recipient)
# For debugging, we can try to use a hardcoded number if known, or ask the user.
# For now, I will put a placeholder and ask the user to run it or I will try to read the logs to see a valid number.
# Actually, I can't know the user's number easily. 
# I will make the script accept a number as input or just print the request to verify structure.

def test_typing_indicator(to_number):
    print(f"Testing typing indicator for {to_number}...")
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    versions = ["v21.0", "v17.0", "v16.0"]
    
    for version in versions:
        print(f"--- Testing Version: {version} ---")
        url = f"https://graph.facebook.com/{version}/{PHONE_NUMBER_ID}/messages"
        
        # Test standard sender_action
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "sender_action": "typing_on" 
        }
        
        try:
            res = requests.post(url, json=payload, headers=headers)
            print(f"Payload: {payload}")
            print(f"Response: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Error: {e}")
        print("\n")

    # Let's try sending a dummy text message to see if *that* works (permissions check)
    print("--- Test 2: Text Message (Permissions Check) ---")
    payload_text = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": "Debug test message"}
    }
    try:
        url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
        res = requests.post(url, json=payload_text, headers=headers)
        print(f"Response: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    # verification
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Missing credentials.")
    else:
        # Check for command line argument
        if len(sys.argv) > 1:
            number = sys.argv[1]
            test_typing_indicator(number)
        else:
            print("Please provide a phone number as an argument: python debug_typing.py <phone_number>")
