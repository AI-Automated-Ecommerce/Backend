import os
import re
import json
import datetime
from typing import TypedDict, Annotated, List, Union, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Product, Category, BusinessSettings
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from langgraph.graph.message import add_messages

# Define the Agent State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    session_data: Dict[str, Any]
    user_id: str

class AIAgent:
    """
    Intelligent Sales Assistant AI Agent for E-commerce Store using LangGraph.
    """
    
    def __init__(self):
        """Initialize the AI agent with Google Gemini API and LangGraph."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        self.frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
        
        if not api_key:
            print("WARNING: GOOGLE_API_KEY not found in environment variables.")

        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.7
        )

        # Initialize tools
        self.tools = [self.search_products, self.get_business_info]
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Build the graph
        workflow = StateGraph(AgentState)

        # Define nodes
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", ToolNode(self.tools))

        # Define edges
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        workflow.add_edge("tools", "agent")

        # Initialize memory
        self.memory = MemorySaver()
        
        # Compile the graph
        self.app = workflow.compile(checkpointer=self.memory)
        
        # Path to save chat logs
        self.log_file = "chat_logs.json"

    # --- TOOLS ---

    @staticmethod
    @tool
    def search_products(query: str, category_filter: str = None) -> str:
        """
        Search for products in the store based on a query. 
        Use this tool when the user asks about products, availability, or prices.
        
        Args:
            query: The search query (e.g., "headphones", "wireless mouse").
            category_filter: Optional category ID to filter results.
        
        Returns:
            A string containing details of matching products.
        """
        print(f"DEBUG: TOOL search_products called with query='{query}' kwargs={{'category_filter': '{category_filter}'}}")
        # Note: In a real scenario, we'd need to inject the DB session.
        # For this refactor, we will rely on a globally available session or creating one.
        # Since tools are static, we'll create a new session here.
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            # Clean query
            cleaned_query = re.sub(r'[^\w\s]', '', query.lower())
            query_words = [w for w in cleaned_query.split() if w and len(w) > 2]
            
            # Check if query is generic (user wants to browse all products)
            generic_terms = {'products', 'items', 'inventory', 'catalog', 'stock', 'available', 'list', 'all', 'everything', 'show', 'have', 'sell', 'offer'}
            is_generic = any(word in generic_terms for word in cleaned_query.split())

            products_query = db.query(Product).filter(Product.isActive == True)
            if category_filter:
                products_query = products_query.filter(Product.categoryId == category_filter)
            
            all_products = products_query.all()
            
            scored_products = []
            
            if not is_generic:
                # Specific search: score by keyword relevance
                for product in all_products:
                    score = 0
                    prod_text = (product.name + " " + (product.description or "")).lower()
                    
                    if query.lower() in product.name.lower():
                        score += 5
                    
                    for word in query_words:
                        if word in prod_text:
                            score += 1
                    
                    if score > 0:
                        scored_products.append((product, score))
            
            # If generic query OR keyword search found nothing, return all products
            if is_generic or not scored_products:
                scored_products = [(p, 1) for p in all_products]
            
            scored_products.sort(key=lambda x: x[1], reverse=True)
            top_products = [p for p, s in scored_products[:5]]
            
            if not top_products:
                result = "No products found matching that description."
            else:
                result = "Found the following products:\n"
                for p in top_products:
                    stock_status = f"{p.stockQuantity} in stock" if p.stockQuantity > 0 else "Out of stock"
                    result += f"- {p.name} (ID: {p.id}): ${p.price}. {p.description or ''} [{stock_status}] Image: {p.imageUrl}\n"
            
            print(f"DEBUG: TOOL search_products returning: {result[:100]}...")
            return result
        finally:
            db.close()

    @staticmethod
    @tool
    def get_business_info() -> str:
        """
        Get contact details and general information about the business.
        Use this tool when the user asks for contact info, address, email, or about the company.
        """
        print("DEBUG: TOOL get_business_info called")
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            settings = db.query(BusinessSettings).first()
            if not settings:
                return "Business information is not configured."
            
            info = f"Business Name: {settings.business_name}\n"
            if settings.contact_phone: info += f"Phone: {settings.contact_phone}\n"
            if settings.whatsapp_number: info += f"WhatsApp: {settings.whatsapp_number}\n"
            if settings.contact_email: info += f"Email: {settings.contact_email}\n"
            if settings.address: info += f"Address: {settings.address}\n"
            
            print(f"DEBUG: TOOL get_business_info returning: {info[:100]}...")
            return info
        finally:
            db.close()

    # --- NODE FUNCTIONS ---

    def call_model(self, state: AgentState):
        messages = state['messages']
        print(f"DEBUG: call_model invoked. Message count: {len(messages)}")
        for i, msg in enumerate(messages):
            print(f"DEBUG: Msg {i}: Type={type(msg).__name__}, Content='{msg.content}', ToolCalls={getattr(msg, 'tool_calls', 'N/A')}")
        
        response = self.llm_with_tools.invoke(messages)
        print(f"DEBUG: LLM Response: Content='{response.content}', ToolCalls={response.tool_calls}")
        return {"messages": [response]}

    def should_continue(self, state: AgentState):
        messages = state['messages']
        last_message = messages[-1]
        
        if last_message.tool_calls:
            return "continue"
        return "end"

    # --- PUBLIC INTERFACE ---

    def generate_response(self, user_query: str, db: Session, user_id: str) -> str:
        """
        Generate AI response to user query using LangGraph.
        """
        # Validate query (Keep existing validation logic if needed, or rely on LLM)
        # We'll run a quick pre-check to block obvious malicious intent
        if not self._validate_query(user_query):
            return "I cannot process that request."

        # Config for the thread
        config = {"configurable": {"thread_id": user_id}}
        
        # Initial state
        # We need to fetch history if not already in memory (LangGraph Checkpointer handles persistence if configured correctly)
        # For this refactor, we are using MemorySaver which is in-memory. 
        # So we might start fresh or rely on the thread_id to resume.
        
        # Prepare the input
        # We can also inject a system message here
        system_prompt = self._get_system_prompt(db)
        
        # Run the graph
        # We verify if the thread exists, if not we start with system prompt
        # Actually, `app.invoke` or `stream` is better.
        
        # NOTE: To maintain conversation history with MemorySaver, we just pass the new user message.
        # The graph state (messages) will be updated.
        # However, we need to ensure the SystemMessage is there at the beginning.
        
        current_state = self.app.get_state(config)
        
        inputs = None
        if not current_state.values:
             # Prepend system prompt to user query to ensure compatibility with all model versions/SDKs
             combined_query = f"System Instruction: {system_prompt}\n\nUser Query: {user_query}"
             inputs = {"messages": [HumanMessage(content=combined_query)], "user_id": user_id, "session_data": {}}
        else:
             inputs = {"messages": [HumanMessage(content=user_query)]}
            
        # We'll use invoke to get the final result
        result = self.app.invoke(inputs, config=config)
        
        # Extract the last message content
        last_message = result['messages'][-1]
        response_text = last_message.content
        
        # Handle case where response is a list (new SDK behavior)
        if isinstance(response_text, list):
            # It might be [{'type': 'text', 'text': '...'}]
            text_parts = []
            for part in response_text:
                if isinstance(part, dict) and 'text' in part:
                    text_parts.append(part['text'])
                elif isinstance(part, str):
                    text_parts.append(part)
            response_text = " ".join(text_parts)
        
        # Log interaction (Keep existing logging)
        # self._log_interaction(user_id, user_query, "", response_text)
        
        return response_text

    def generate_response_with_images(self, user_query: str, db: Session, user_id: str) -> dict:
        """
        Generate AI response and include product images.
        """
        response_text = self.generate_response(user_query, db, user_id)
        
        # Simple heuristic to extract images from the response or previous context
        # Since the tool returns image URLs, the LLM might include them in the text.
        # We can parse them out or do a separate lookup.
        # For backward compatibility, let's try to extract from the tool output if possible, 
        # or just run a quick search like before if the text implies images.
        
        images = []
        # Check if the response contains image references or if we should show images
        if "Image:" in response_text or self._should_show_images(user_query):
             # We can re-use the search tool logic or parse the response
             pass
             # For now, let's do a targeted search just for images to ensure the UI gets them
             # This is a bit redundant but ensures the frontend contract is met
             images = self._get_product_images(user_query, db)

        return {
            "text": response_text,
            "images": images
        }

    # --- HELPERS (Ported from original) ---

    def _get_system_prompt(self, db: Session) -> str:
        settings = db.query(BusinessSettings).first()
        business_name = settings.business_name if settings else "our store"
        
        return f"""You are a helpful Sales Assistant for {business_name}.
        Your goal is to assist customers, provide product information, and help them with their needs.
        
        You have access to tools to search for products and get business contact information.
        ALWAYS use the 'search_products' tool when potential customers ask about products, prices, or availability.
        ALWAYS use the 'get_business_info' tool when asked for contact details, address, or email.
        
        If the user wants to buy something, guide them to provide necessary details (Name, Address, Phone).
        Once you have all details, provide a summary (Note: Tool for order placement is not yet active, just summarize).
        
        Be polite, professional, and concise.
        """

    def _validate_query(self, query: str) -> bool:
        """Simple security check."""
        query_lower = query.lower()
        blocked = ['drop table', 'delete from', 'insert into', 'update user']
        return not any(b in query_lower for b in blocked)
        
    def _should_show_images(self, query: str) -> bool:
        image_keywords = ['show', 'image', 'picture', 'photo', 'look', 'see']
        return any(kw in query.lower() for kw in image_keywords)

    def _get_product_images(self, query: str, db: Session) -> list:
        # Re-implement simplified version for compatibility
        # This mirrors the old logic just to satisfy the frontend's need for structured image data
        # In a pure agentic world, the agent would return the images in the content_block
        from app.models.models import Product
        
        cleaned = re.sub(r'[^\w\s]', '', query.lower())
        words = cleaned.split()
        
        products = db.query(Product).filter(Product.isActive == True).all()
        matches = []
        
        for p in products:
            if query.lower() in p.name.lower():
                matches.append(p)
            elif any(w in p.name.lower() for w in words if len(w)>2):
                matches.append(p)
                
        images = []
        for p in matches[:3]:
            if p.imageUrl:
                images.append({
                    "product_id": p.id,
                    "product_name": p.name,
                    "price": float(p.price),
                    "image_url": p.imageUrl,
                    "stock": p.stockQuantity
                })
        return images
    
    def clear_history(self, user_id: str):
        # Reset memory for the thread
        config = {"configurable": {"thread_id": user_id}}
        # LangGraph MemorySaver doesn't have a direct 'clear' method exposed easily on the instance 
        # without accessing internal storage, but we can start a new thread or just ignore.
        # For this simple implementation, we might not truly clear the persistent checkpointer 
        # unless we implement a custom one. 
        # But we can update the state to empty.
        # self.app.update_state(config, {"messages": []}) # This might append.
        pass

# Singleton instance
agent = AIAgent()

if __name__ == "__main__":
    # Test block
    print("Agent initialized.")
