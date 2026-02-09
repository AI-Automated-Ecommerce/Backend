import os
import re
import json
import datetime
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
        self.frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
        
        self.client = None
        if api_key and api_key.startswith("gsk_"):
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                print(f"Failed to init Groq: {e}")
        
        # In-memory conversation history: {user_id: [{role, content}, ...]}
        self.conversation_history = {}
        
        # Structured session memory for order details: {user_id: {name, address, phone, email, product_id, product_name, quantity}}
        self.session_memory = {}
        
        # Path to save chat logs for fine-tuning
        self.log_file = "chat_logs.json"
        
        # Enhanced system prompt with clear guidelines
        self.system_prompt = f"""
        You are an elite, intelligent Sales Assistant for an e-commerce store.
        Your goal is to provide accurate, helpful, and detailed product information.

        CAPABILITIES:
        1.  **Product Knowledge**: Answer questions about products from the "Context Information" provided.
        2.  **Order Processing**: ONLY when user explicitly wants to buy/order, collect details and generate checkout links.
        3.  **Comparisons**: Compare products based on price, specs, and features.

        STRICT RULES:
        *   **Context Only**: Do NOT hallucinate products. If it's not in the context, we don't sell it.
        *   **Prices**: Always mention prices in USD ($).
        *   **Stock**: Check stock levels. If stock is 0, you CANNOT sell it.
        *   **Tone**: Professional, enthusiastic, and helpful. Use emojis like 📦, 💳, ✨ where appropriate.
        *   **DO NOT be pushy**: When user asks about products, ONLY answer their question. 
            - Do NOT say "would you like to buy?" or "ready to order?" or "let me know when you want to proceed"
            - Simply provide the product info and stop. Let the user decide on their own.

        ⚠️ CRITICAL: WHEN TO ASK FOR ORDER DETAILS ⚠️
        - PRODUCT INQUIRY (e.g., "what headphones do you have?", "tell me about the watch", "show me products"):
          → ONLY provide product info. End your response there. No sales pitch.
        
        - ORDER INTENT (e.g., "I want to buy", "order 2 headphones", "I'll take it", "purchase", "place order"):
          → NOW ask for order details (name, address, phone, email)
        
        ORDER PLACEMENT PROTOCOL (Only when user wants to order):
        1. Detect ORDER INTENT: User must say buy/order/purchase/get it/take it/want it
        2. Check Stock (if 0, apologize and suggest alternatives)
        3. Check SESSION STATE for already collected details - NEVER re-ask for those!
        4. Ask ONLY for missing details (name, address, phone, email)
        5. Once ALL details are present, generate checkout link:
           [Click here to confirm the order and payment]({self.frontend_url}/checkout?productId=PRODUCT_ID&quantity=QTY&name=NAME&address=ADDRESS&phone=PHONE&email=EMAIL)
           
           Replace values and URL-encode spaces as %20.
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
        # Improved generic detection to catch typos like "avaibale" or variations
        is_generic = any(phrase in cleaned_query for phrase in [
            "what do you have",
            "what do you sell",
            "show me everything",
            "all products",
            "what products",
            "list products",
            "available"
        ])
        
        # Also treat as generic if the user just asks "products?" or "items?"
        if len(query_words) < 2 and any(w in ["products", "items", "catalog", "stock"] for w in query_words):
            is_generic = True
        
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
        # If the user is providing details (which won't match a product), we MUST recover the previous product context.
        if not relevant_products and user_id and user_id in self.conversation_history:
            history = self.conversation_history[user_id]
            
            # Look back at the last 3 user messages to find what we were talking about
            # This is critical for flow retention (e.g., User says "My name is John" after "I want a headset")
            recent_user_msgs = [msg['content'] for msg in reversed(history) if msg['role'] == 'user'][:3]
            
            for past_msg in recent_user_msgs:
                # Try to find products in previous messages
                found_products = self._find_products(past_msg, db)
                if found_products:
                    relevant_products = found_products
                    break

        if not relevant_products:
            # Check if it looks like the user is providing order details (email, phone, address fragments)
            # and soften the "No products found" message so the AI doesn't hallucinate.
            is_providing_info = any(
                x in query.lower() for x in ['@', 'road', 'st', 'ave', 'lane', '07', 'number', 'name', 'address']
            )
            if is_providing_info:
                 return "User is providing order details. No specific products mentioned in this immediate query, but proceed with the existing order context."
            
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

    def _log_interaction(self, user_id: str, user_query: str, context: str, ai_response: str):
        """
        Log the interaction to a JSON file for future fine-tuning.
        Structure matches common fine-tuning datasets (instruction, input, output).
        """
        log_entry = {
            "timestamp":  datetime.datetime.now().isoformat(),
            "user_id": user_id,
            "instruction": self.system_prompt,
            "input": f"Context:\n{context}\n\nUser: {user_query}",
            "output": ai_response
        }
        
        try:
            # Read existing logs or create new list
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    try:
                        logs = json.load(f)
                    except json.JSONDecodeError:
                        logs = []
            else:
                logs = []
            
            logs.append(log_entry)
            
            # Write back to file
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Failed to log conversation: {e}")

    def _get_session(self, user_id: str) -> dict:
        """Get or initialize session memory for a user."""
        if user_id not in self.session_memory:
            self.session_memory[user_id] = {
                "name": None,
                "address": None,
                "phone": None,
                "email": None,
                "product_id": None,
                "product_name": None,
                "quantity": 1
            }
        return self.session_memory[user_id]

    def _extract_details(self, text: str, session: dict) -> dict:
        """
        Extract user details from message and update session.
        More flexible extraction that works with various input formats.
        """
        text_lower = text.lower()
        
        # Extract email (most reliable pattern)
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            session["email"] = email_match.group()
        
        # Extract phone number (very flexible - any 7+ digit sequence)
        phone_patterns = [
            r'(?:phone|contact|mobile|cell|tel)[:\s]*([+\d\s\-()]{7,})',
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
            r'\b0\d{9,10}\b',  # Sri Lankan format: 0771234567
            r'\b\+94\d{9}\b',  # Sri Lankan with country code
        ]
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text, re.IGNORECASE)
            if phone_match:
                phone = phone_match.group(1) if phone_match.lastindex else phone_match.group()
                phone = re.sub(r'[^\d+]', '', phone)  # Keep only digits and +
                if len(phone) >= 7:
                    session["phone"] = phone
                    break
        
        # Extract name - more flexible patterns
        name_patterns = [
            r"(?:my name is|name is|name[:\s]+)\s*([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
            r"(?:^|\s)([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s|,|$)",  # Two capitalized words
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                # Exclude common non-name words and phrases
                excluded = ['the order', 'my order', 'an order', 'this order', 'new order',
                            'want to', 'going to', 'like to', 'need to', 'have to',
                            'headphones', 'keyboard', 'mouse', 'watch', 'coffee']
                if name.lower() not in excluded and len(name) > 2:
                    session["name"] = name.title()
                    break
        
        # Extract address - very flexible
        address_patterns = [
            r"(?:address|ship to|deliver to|shipping|delivery)(?:\s+is)?[:\s]+(.+?)(?:,?\s*(?:phone|email|contact|mobile)|$)",
            r"(?:address|ship to|deliver to)(?:\s+is)?[:\s]+(.+)",
        ]
        for pattern in address_patterns:
            addr_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if addr_match:
                addr = addr_match.group(1).strip()
                # Clean up - remove leading "is" if present
                addr = re.sub(r'^is\s+', '', addr, flags=re.IGNORECASE)
                addr = re.sub(r'\s*(phone|email|contact|mobile).*$', '', addr, flags=re.IGNORECASE)
                addr = re.sub(r'\s+', ' ', addr).strip()
                if len(addr) > 5:
                    session["address"] = addr
                    break
        
        # Also try to find address-like text with street/road keywords
        if not session.get("address"):
            addr_keywords = re.search(
                r'(\d+[,\s]+[\w\s]+(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|way|place|pl|no\.|number)[\w\s,]+)',
                text, re.IGNORECASE
            )
            if addr_keywords:
                session["address"] = addr_keywords.group(1).strip()
        
        return session

    def _get_session_state_prompt(self, session: dict) -> str:
        """Generate a prompt snippet describing current session state."""
        collected = []
        missing = []
        
        if session.get("product_name"):
            collected.append(f"Product: {session['product_name']} (ID: {session['product_id']}) x{session['quantity']}")
        
        for field in ["name", "address", "phone", "email"]:
            if session.get(field):
                collected.append(f"{field.title()}: {session[field]}")
            else:
                missing.append(field.title())
        
        state = ""
        if collected:
            state += "ALREADY COLLECTED FROM USER (Do NOT ask again):\n- " + "\n- ".join(collected) + "\n\n"
        if missing:
            state += "STILL NEEDED (Ask for these):\n- " + ", ".join(missing) + "\n"
        
        return state

    def generate_response(self, user_query: str, db: Session, user_id: str) -> str:
        """
        Generate AI response to user query.
        
        SECURITY: Only provides information from Product and Category tables.
        """
        # Validate query
        if not self._validate_query(user_query):
            return "I can only help you with product information and availability. I cannot access order history, user data, or payment information."
        
        # Get or initialize session memory
        session = self._get_session(user_id)
        
        # Extract any user details from current message
        self._extract_details(user_query, session)
        
        # Check if user mentions a product and update session
        relevant_products = self._find_products(user_query, db)
        if relevant_products and not session.get("product_name"):
            # Auto-select the first matching product
            product = relevant_products[0]
            session["product_id"] = product.id
            session["product_name"] = product.name
        
        # Extract quantity if mentioned
        qty_match = re.search(r'(\d+)\s*(?:headphones?|watch(?:es)?|keyboard|mouse|coffee|units?|pieces?|items?)', user_query, re.IGNORECASE)
        if qty_match:
            session["quantity"] = int(qty_match.group(1))
        
        # Get product context
        context = self.get_product_context(user_query, db, user_id)
        
        # Get session state for prompt injection
        session_state = self._get_session_state_prompt(session)
        
        # Fallback if no Groq API key
        if not self.client:
            return f"[MOCK AI] Asked: '{user_query}'.\n\nFound:\n{context}\n\nSession: {session}\n\n(Set GROQ_API_KEY in .env for real AI responses)"

        # Get conversation history
        user_history = self.conversation_history.get(user_id, [])
        
        # Build messages for AI
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(user_history[-10:])  # Last 10 messages for context
        messages.append({
            "role": "user",
            "content": f"SESSION STATE (VERY IMPORTANT - Use this info, do NOT re-ask for collected data):\n{session_state}\n\nContext Information:\n{context}\n\nUser Question: {user_query}"
        })

        try:
            # Call Groq API with llama-3.3-70b
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=1024
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
            
            # Log this interaction for future fine-tuning
            self._log_interaction(user_id, user_query, context, ai_response)
            
            return ai_response
            
        except Exception as e:
            return f"Error connecting to AI service: {str(e)}"

    def clear_history(self, user_id: str, clear_session: bool = True):
        """Clear conversation history and optionally session memory for a user."""
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
        if clear_session and user_id in self.session_memory:
            del self.session_memory[user_id]


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
