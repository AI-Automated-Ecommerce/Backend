import sys
import os

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_agent import agent
from app.core.database import SessionLocal
from langchain_core.messages import ToolMessage

def test_image_extraction():
    print("Testing Image Extraction Logic...")
    
    # Mock a tool output that mimics search_products
    # We do this by manually injecting a ToolMessage into the agent's logic effectively, 
    # OR simpler: we can just call the method _run_agent if we could mock the graph execution.
    # But since we can't easily mock the graph inside the running agent without patching,
    # let's try to actually run it against the real agent if we have credentials.
    
    # However, running the real agent requires valid API keys and DB.
    # The environment seems to have them (running uvicorn).
    
    # Let's try to unit test the extraction logic specifically if possible, 
    # but `generate_response_with_images` couples execution and extraction.
    
    # Alternative: We can subclass or MonkeyPatch the agent for this test
    # to return a pre-canned result from _run_agent, and then test the extraction.
    
    original_run_agent = agent._run_agent
    
    class MockResult:
        def __init__(self, messages):
            self.messages = messages
            
        def __getitem__(self, key):
            if key == 'messages': return self.messages
            return None
            
    def mock_run_agent(user_query, db, user_id):
        print(f"Mocking agent run for query: {user_query}")
        
        # Create a mock conversation trace
        # 1. User asks for products
        # 2. Agent calls tool
        # 3. Tool returns products (with images)
        # 4. Agent replies text
        
        from langchain_core.messages import HumanMessage, AIMessage
        
        # Tool output matching search_products format
        tool_output = (
            "Found the following products:\n"
            "- Red T-Shirt (ID: 101): $15.00. A nice red shirt. [10 in stock] Image: https://example.com/red-shirt.jpg\n"
            "- Blue Jeans (ID: 102): $40.50. Comfortable jeans. [5 in stock] Image: https://example.com/blue-jeans.jpg\n"
        )
        
        messages = [
            HumanMessage(content="Show me red shirts"),
            AIMessage(content="", tool_calls=[{'name': 'search_products', 'args': {}, 'id': 'call_1'}]),
            ToolMessage(content=tool_output, tool_call_id='call_1', name='search_products'),
            AIMessage(content="Here are the red shirts I found.")
        ]
        
        return {"messages": messages}
        
    # Patch
    agent._run_agent = mock_run_agent
    
    try:
        db = SessionLocal()
        result = agent.generate_response_with_images("Show me red shirts", db, "test_user_123")
        
        print("\nResult:")
        print(f"Text: {result['text']}")
        print(f"Images: {len(result['images'])}")
        for img in result['images']:
            print(f" - {img['product_name']}: {img['image_url']} (${img['price']})")
            
        # Assertions
        assert len(result['images']) == 2
        assert result['images'][0]['image_url'] == "https://example.com/red-shirt.jpg"
        assert result['images'][0]['price'] == 15.0
        assert result['images'][1]['product_name'] == "Blue Jeans"
        
        print("\n✅ Verification Successful: Images correctly extracted from tool output.")
        
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore
        agent._run_agent = original_run_agent
        db.close()

if __name__ == "__main__":
    test_image_extraction()
