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

@tool
def get_product_images(product_name_or_id: str) -> str:
    """
    Get the image and details of a SPECIFIC product.
    Use this tool when the user asks to see a specific product (e.g. "show me the red one", "what does the first one look like?").
    
    Args:
        product_name_or_id: The name or ID of the product to find.
    
    Returns:
        String with product details and image URL.
    """
    print(f"DEBUG: TOOL get_product_images called with product_name_or_id='{product_name_or_id}'")
    from app.core.database import SessionLocal
    from app.models.models import Product
    
    db = SessionLocal()
    try:
        # Try finding by ID first if it looks like an ID
        product = None
        if product_name_or_id.isdigit():
            product = db.query(Product).filter(Product.id == int(product_name_or_id)).first()
            
        # If not found by ID, search by name
        if not product:
            # Simple case-insensitive search
            products = db.query(Product).filter(Product.isActive == True).all()
            # 1. Exact match
            for p in products:
                if p.name.lower() == product_name_or_id.lower():
                    product = p
                    break
            
            # 2. Fuzzy match / Partial containing match
            if not product:
                for p in products:
                    if product_name_or_id.lower() in p.name.lower():
                        product = p
                        break
        
        if product:
            stock_status = f"{product.stockQuantity} in stock" if product.stockQuantity > 0 else "Out of stock"
            result = f"Found product:\n- {product.name} (ID: {product.id}): ${product.price}. {product.description or ''} [{stock_status}] Image: {product.imageUrl}"
        else:
            result = f"Could not find a specific product matching '{product_name_or_id}'."
            
        print(f"DEBUG: TOOL get_product_images returning: {result}")
        return result
    finally:
        db.close()
