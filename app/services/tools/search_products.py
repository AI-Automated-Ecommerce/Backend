import re
from langchain_core.tools import tool


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
    from app.models.models import Product
    
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
