import os
import re
from sqlalchemy.orm import Session
from app.models.models import Product, Category
from groq import Groq


class AIAgent:
    """
    Intelligent Sales Assistant AI Agent for E-commerce Store.
    
    SECURITY: This agent is RESTRICTED to accessing ONLY the Product and Category tables.
    It CANNOT access User, Order, or any other sensitive data tables.
    """
    
    # Explicitly define allowed tables for security
    ALLOWED_TABLES = ['Product', 'Category']
    
    def __init__(self):
        """Initialize the AI agent with Groq API and conversation history."""
        api_key = os.environ.get("GROQ_API_KEY")
        self.client = None
        if api_key and api_key.startswith("gsk_"):
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                print(f"Failed to init Groq: {e}")
        
        # In-memory conversation history: {user_id: [{role, content}, ...]}
        self.conversation_history = {}
        
        # Enhanced system prompt with clear guidelines
        self.system_prompt = """
        You are an intelligent Sales Assistant for an e-commerce store.
        
        Your Goals:
        1. Help users explore products (features, price, stock).
        2. Facilitate order placement by collecting necessary details.
        3. Generate a checkout link ONLY when all details are verified.
        
        Order Placement Process:
        If the user indicates they want to buy something (e.g., "place order", "buy this"):
        1. Identify the Product ID and Quantity.
        2. Check Stock: If stock is 0, apologize and refuse.
        3. Collect Missing Details: You MUST ask for the following if not provided:
           - Customer Name
           - Shipping Address
           - Phone Number
        4. Confirm: Summarize the order (Product, Qty, Price, Name, Address) and ask for confirmation.
        5. Generate Link: Only after confirmation, provide the link:
           [Click here to Order {Product Name}](http://localhost:8080/checkout?productId={ID}&quantity={Qty}&name={Name}&address={Address}&phone={Phone})
        
        Strict Guidelines:
        - NEVER invent products. Use "Context Information" only.
        - If "Context Information" is empty or product missing, ask clarifying questions.
        - Be friendly, professional, and concise.
        - Use emojis effectively 📦 ✅ 💳.
        """

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for searching."""
        return re.sub(r'[^\w\s]', '', text.lower())

    def _validate_query(self, query: str) -> bool:
        """
        Validate user query for security.
        Reject queries that attempt to access restricted data.
        """
        query_lower = query.lower()
        
        # Blocked keywords that might indicate attempts to access restricted data
        # RELAXED for order taking: allowed 'address', 'card', 'user', 'customer'
        blocked_keywords = [
            'password', 'admin', 'delete', 'update',
            'insert', 'drop', 'table', 'database', 'sql'
        ]
        
        # Check for SQL injection attempts or restricted data access
        # Use regex to match whole words only to avoid false positives like "headphones"
        for keyword in blocked_keywords:
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, query_lower):
                return False
        
        return True

    def _find_products(self, text: str, db: Session, category_filter: str = None) -> list:
        """
        Find relevant products based on user query.
        
        SECURITY: Only queries the Product table with active products.
        """
        cleaned_query = self._clean_text(text)
        query_words = [w for w in cleaned_query.split() if w and len(w) > 2]
        
        if not query_words:
            return []

        # Check for generic queries
        is_generic = any(phrase in cleaned_query for phrase in [
            "what do you have",
            "what do you sell",
            "show me everything",
            "all products",
            "what products"
        ])
        
        # SECURITY: Only query Product table with isActive filter
        products_query = db.query(Product).filter(Product.isActive == True)
        
        # Apply category filter if specified
        if category_filter:
            products_query = products_query.filter(Product.categoryId == category_filter)
        
        products = products_query.all()
        
        scored_products = []
        
        for product in products:
            # Create searchable corpus for the product
            product_corpus = self._clean_text(
                f"{product.name} {product.description or ''}"
            ).split()
            
            # Calculate relevance score
            score = 0
            for query_word in query_words:
                # Higher score for name matches
                if query_word in product.name.lower():
                    score += 3
                # Medium score for description matches
                elif query_word in product_corpus:
                    score += 1
            
            # Include all products for generic queries, or scored products
            if is_generic or score > 0:
                scored_products.append((product, score))
        
        # Sort by relevance score (highest first)
        scored_products.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 5 most relevant products
        return [product for product, _ in scored_products[:5]]

    def _get_categories(self, db: Session) -> list:
        """
        Get all active categories.
        
        SECURITY: Only queries the Category table.
        """
        return db.query(Category).all()

    def get_product_context(self, query: str, db: Session, user_id: str = None) -> str:
        """
        Build context information about relevant products.
        
        SECURITY: Only accesses Product and Category tables.
        """
        # Validate query for security
        if not self._validate_query(query):
            return "I can only help you with product information and availability. Please ask about our products!"
        
        # Search for relevant products
        relevant_products = self._find_products(query, db)
        
        # Check conversation history for follow-up context
        if not relevant_products and user_id and user_id in self.conversation_history:
            history = self.conversation_history[user_id]
            last_user_msg = next(
                (msg['content'] for msg in reversed(history) if msg['role'] == 'user'),
                None
            )
            
            # Detect follow-up questions
            follow_up_triggers = ["it", "them", "that", "price", "cost", "much", "stock", "available"]
            if last_user_msg and any(trigger in query.lower() for trigger in follow_up_triggers):
                relevant_products = self._find_products(last_user_msg, db)

        if not relevant_products:
            return "No products found matching that description. Try asking about specific product types or categories!"
        
        # Build context with product information
        context_lines = []
        seen_ids = set()
        
        for product in relevant_products:
            if product.id not in seen_ids:
                seen_ids.add(product.id)
                stock_status = f"{product.stockQuantity} in stock" if product.stockQuantity > 0 else "Out of stock"
                context_lines.append(
                    f"- **{product.name}** (ID: {product.id}) - ${product.price}: {product.description or 'No description'} "
                    f"[{stock_status}]"
                )
        
        return "Here are the products we have available:\n" + "\n".join(context_lines)

    def generate_response(self, user_query: str, db: Session, user_id: str) -> str:
        """
        Generate AI response to user query.
        
        SECURITY: Only provides information from Product and Category tables.
        """
        # Validate query
        if not self._validate_query(user_query):
            return "I can only help you with product information and availability. I cannot access order history, user data, or payment information."
        
        # Get product context
        context = self.get_product_context(user_query, db, user_id)
        
        # Fallback if no Groq API key
        if not self.client:
            return f"[MOCK AI] Asked: '{user_query}'.\n\nFound:\n{context}\n\n(Set GROQ_API_KEY in .env for real AI responses)"

        # Get conversation history
        user_history = self.conversation_history.get(user_id, [])
        
        # Build messages for AI
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(user_history[-10:])  # Last 10 messages for context
        messages.append({
            "role": "user",
            "content": f"Context Information:\n{context}\n\nUser Question: {user_query}"
        })

        try:
            # Call Groq API
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=500
            )
            ai_response = chat_completion.choices[0].message.content
            
            # Store conversation history
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            self.conversation_history[user_id].append({
                "role": "user",
                "content": user_query
            })
            self.conversation_history[user_id].append({
                "role": "assistant",
                "content": ai_response
            })
            
            # Limit history to last 20 messages (10 exchanges)
            if len(self.conversation_history[user_id]) > 20:
                self.conversation_history[user_id] = self.conversation_history[user_id][-20:]
            
            return ai_response
            
        except Exception as e:
            return f"Error connecting to AI service: {str(e)}"

    def clear_history(self, user_id: str):
        """Clear conversation history for a specific user."""
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]


# Singleton instance
agent = AIAgent()


if __name__ == "__main__":
    import sys
    import os
    
    # Add the project root to sys.path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "../.."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from app.core.database import SessionLocal
    
    # Interactive CLI
    print("="*60)
    print("🤖 Smart Sales Agent (Interactive Debug Mode)")
    print("Type 'exit' or 'quit' to stop.")
    print("="*60)
    
    db = SessionLocal()
    user_id = "debug_user"
    
    # Pre-seed history to test flow if needed, or start fresh
    agent.clear_history(user_id)
    
    try:
        while True:
            try:
                user_input = input("\nYou: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ['quit', 'exit']:
                    print("Goodbye!")
                    break
                    
                response = agent.generate_response(user_input, db, user_id)
                print(f"AI:  {response}")
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()
