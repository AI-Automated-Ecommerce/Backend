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
from langgraph.checkpoint.memory import MemorySaver

from langgraph.graph.message import add_messages

# Import tools from the tools module
from app.services.tools import (
    search_products,
    get_product_images,
    get_business_info,
    get_payment_details,
    add_to_cart,
    view_cart,
    generate_invoice,
    get_business_details_tool,
    confirm_user_payment
)
from app.services.chat_history import get_chat_history

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
        self.tools = [search_products, get_product_images, get_business_info, add_to_cart, view_cart, generate_invoice, get_payment_details, get_business_details_tool, confirm_user_payment]
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

    def _run_agent(self, user_query: str, db: Session, user_id: str) -> dict:
        """
        Internal method to run the agent and return the full state.
        """
        # Validate query
        if not self._validate_query(user_query):
            return {"messages": [AIMessage(content="I cannot process that request.")]}

        # Config for the thread
        config = {"configurable": {"thread_id": user_id}}
        
        # Get system prompt
        system_prompt = self._get_system_prompt(db)
        
        current_state = self.app.get_state(config)
        
        # Retrieve conversation history (simplified for brevity, reliable on graph state + input injection)
        history_msgs = get_chat_history(db, user_id, limit=5)
        history_prompts = []
        for msg in history_msgs:
            if not msg.content or not msg.content.strip(): continue
            if msg.role == 'user': history_prompts.append(HumanMessage(content=msg.content))
            else: history_prompts.append(AIMessage(content=msg.content))
        
        inputs = None
        if not current_state.values:
             detected_lang = self.detect_language(user_query)
             is_first_message = len(history_prompts) == 0
             greeting_instruction = ""
             if is_first_message:
                 greeting_instruction = f"This is the first message from the user. You MUST start with a warm greeting in {detected_lang}."

             combined_query = (f"System Instruction: {system_prompt}\n"
                               f"IMPORTANT: The user is speaking in {detected_lang}. You MUST reply in {detected_lang} ONLY.\n"
                               f"{greeting_instruction}\n"
                               f"IMPORTANT: When a user wants to buy something:\n"
                               f"1. Use 'generate_invoice' tool to create an order summary.\n"
                               f"2. Ask the user to CONFIRM the invoice details.\n"
                               f"3. ONLY after they confirm, use 'get_payment_details' tool to show bank info.\n"
                               f"Previous Context: {history_prompts}\n"
                               f"User Query: {user_query}")
             inputs = {"messages": [HumanMessage(content=combined_query)], "user_id": user_id, "session_data": {}}
        else:
             inputs = {"messages": [HumanMessage(content=user_query)]}
            
        # Invoke the graph
        result = self.app.invoke(inputs, config=config)
        return result

    def generate_response(self, user_query: str, db: Session, user_id: str) -> str:
        """
        Generate AI response to user query (Text only).
        """
        result = self._run_agent(user_query, db, user_id)
        last_message = result['messages'][-1]
        return self._parse_response_text(last_message.content)

    def generate_response_with_images(self, user_query: str, db: Session, user_id: str) -> dict:
        """
        Generate AI response and include product images found by tools.
        """
        result = self._run_agent(user_query, db, user_id)
        last_message = result['messages'][-1]
        response_text = self._parse_response_text(last_message.content)
        
        # Extract images from tool outputs in the conversation
        images = []
        
        messages = result['messages']
        # Only process images if the user explicitly asked for them
        if self._should_show_images(user_query):
            
            # Iterate backwards through messages to find tool outputs in the CURRENT turn
            # We stop when we hit the HumanMessage that started this turn.
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    break
                    
                if hasattr(msg, 'name') and msg.name in ['search_products', 'get_product_images']:
                    # Parse product info from tool output
                    # Output format: "- Name (ID: 1): $10. Desc... [Stock] Image: URL"
                    content = msg.content
                    
                    lines = content.split('\n')
                    for line in lines:
                        if "Image:" in line:
                            try:
                                # Extract URL
                                img_match = re.search(r'Image: (https?://[^\s]+)', line)
                                if img_match:
                                    img_url = img_match.group(1)
                                    
                                    # Extract Name and Price for caption
                                    # "- Product Name (ID: 1): $19.99."
                                    name_match = re.search(r'- (.*?) \(ID:', line)
                                    name = name_match.group(1) if name_match else "Product"
                                    
                                    price_match = re.search(r'\$(\d+\.?\d*)', line)
                                    price = float(price_match.group(1)) if price_match else 0.0
                                    
                                    stock_match = re.search(r'\[(.*?)\]', line)
                                    stock_str = stock_match.group(1) if stock_match else ""
                                    stock = 0
                                    if "in stock" in stock_str:
                                        stock_nums = re.findall(r'\d+', stock_str)
                                        stock = int(stock_nums[0]) if stock_nums else 0

                                    images.append({
                                        "product_name": name,
                                        "price": price,
                                        "image_url": img_url,
                                        "stock": stock
                                    })
                            except Exception as e:
                                print(f"Error parsing product line: {e}")
                    
                    # If we found images from a tool call in this turn, we can stop for that tool
                    # (Though technically multiple tools could be called, usually one suffices)
        
        # Limit images to avoid spamming
        images = images[:5]

        return {
            "text": response_text,
            "images": images
        }

    def _parse_response_text(self, content) -> str:
        """Helper to handle list or string content from LLM"""
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and 'text' in part:
                    text_parts.append(part['text'])
                elif isinstance(part, str):
                    text_parts.append(part)
            return " ".join(text_parts)
        return str(content)

    # --- HELPERS (Ported from original) ---

    def _get_system_prompt(self, db: Session) -> str:
        settings = db.query(BusinessSettings).first()
        business_name = settings.business_name if settings else "our store"
        
        return f"""You are a helpful Sales Assistant for {business_name}.
        Your goal is to assist customers, provide product information, and help them with their needs.
        
        You have access to tools to search for products and get business contact information.
        ALWAYS use the 'search_products' tool when potential customers ask about products, prices, or availability.
        If the user asks to see a SPECIFIC product image or details (e.g. "show me the red one", "how does that look?"), use the 'get_product_images' tool with the specific product name or ID.
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
    
    def detect_language(self, text: str) -> str:
        """
        Detects the language of the input text using the LLM.
        Returns: 'English', 'Sinhala', 'Tamil', or 'Singlish'.
        """
        prompt = f"""
        Analyze the following text and determine its language.
        Possible languages: English, Sinhala, Tamil, Singlish.
        
        Singlish is Sinhala written in English characters (e.g., 'Kohomada' means 'How are you').
        
        Text: '{text}'
        
        Return ONLY the language name.
        """
        response = self.llm.invoke(prompt)
        return response.content.strip()

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


