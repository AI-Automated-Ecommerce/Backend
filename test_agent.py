
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.ai_agent import agent
from app.core.database import SessionLocal

def test_agent():
    print("Testing AI Agent...")
    db = SessionLocal()
    try:
        response = agent.generate_response("Hello, what do you sell?", db, "test_user")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_agent()
