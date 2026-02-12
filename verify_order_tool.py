import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock environment variables BEFORE importing anything that uses them
os.environ["GOOGLE_API_KEY"] = "mock_key"

# Mock database dependencies
sys.modules['app.core.database'] = MagicMock()
sys.modules['app.models.models'] = MagicMock()

from app.services.ai_agent import AIAgent

class TestOrderTool(unittest.TestCase):
    @patch('app.core.database.SessionLocal')
    @patch('app.services.ai_agent.ChatGoogleGenerativeAI')
    def test_place_order(self, mock_llm, mock_session_cls):
        # Setup mock DB session
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        
        # Setup mock products
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.name = "Test Product"
        mock_product.price = 100.0
        mock_product.isActive = True
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_product]
        
        # Setup mock settings
        mock_settings = MagicMock()
        mock_settings.bank_details = "Bank: Mock Bank, Account: 123"
        mock_db.query.return_value.first.return_value = mock_settings
        
        # Call the static tool method directly
        # Note: Since it's a static method wrapped in @tool, we need to access the underlying function
        # But depending on how LangChain's @tool works, it might be callable directly or via .run
        # Let's try calling it as a static method on the class if possible, or just the function if we can import it.
        # Given it's a static method on the class:
        
        # Call the underlying function of the tool
        result = AIAgent.place_order.func(
            customer_name="John Doe",
            customer_address="123 St",
            customer_phone="555-0123",            items="1x Test Product"
        )
        
        print(f"Tool Result: {result}")
        
        # Verify interactions
        self.assertIn("Order #", result)
        self.assertIn("Bank: Mock Bank", result)
        self.assertIn("Test Product", result)
        self.assertIn("$100.00", result)
        
        # Verify DB calls
        # Should add Order and OrderItem
        self.assertTrue(mock_db.add.called)
        self.assertTrue(mock_db.commit.called)

if __name__ == '__main__':
    unittest.main()
