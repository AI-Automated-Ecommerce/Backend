"""
Test script to verify WhatsApp typing indicator functionality.
This simulates a WhatsApp message and checks if typing indicator is sent before reply.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api.endpoints.whatsapp import send_typing_indicator, send_reply
from dotenv import load_dotenv

load_dotenv()

async def test_typing_indicator():
    """
    Test the typing indicator flow:
    1. Send typing indicator
    2. Simulate AI processing delay
    3. Send actual message
    """
    # Use a test phone number (replace with your WhatsApp test number)
    test_number = os.getenv("TEST_WHATSAPP_NUMBER", "YOUR_TEST_NUMBER_HERE")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    print("=" * 60)
    print("WhatsApp Typing Indicator Test")
    print("=" * 60)
    print(f"Test Number: {test_number}")
    print(f"Phone Number ID: {phone_number_id}")
    print()
    
    # Step 1: Send typing indicator
    print("⌨️  Step 1: Sending typing indicator...")
    await send_typing_indicator(test_number, phone_number_id, None)
    print("✅ Typing indicator sent")
    print()
    
    # Step 2: Simulate AI thinking/processing
    print("🤔 Step 2: Simulating AI processing (5 seconds delay)...")
    for i in range(5, 0, -1):
        print(f"   {i} seconds remaining...")
        await asyncio.sleep(1)
    print()
    
    # Step 3: Send actual message
    print("📤 Step 3: Sending actual reply...")
    test_message = "This is a test message to verify typing indicator works correctly! 🎉"
    await send_reply(test_number, test_message, phone_number_id)
    print("✅ Message sent")
    print()
    
    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print()
    print("📱 CHECK YOUR WHATSAPP:")
    print("1. Did you see 'typing...' indicator appear?")
    print("2. Did it stay visible during the 5-second delay?")
    print("3. Did it disappear when the message arrived?")
    print()
    print("If YES to all: ✅ Typing indicator is working correctly")
    print("If NO to any: ⚠️  There may be timing or API issues")

if __name__ == "__main__":
    asyncio.run(test_typing_indicator())
