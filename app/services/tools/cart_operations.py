import re
from langchain_core.tools import tool


@tool
def add_to_cart(items: str, customer_phone: str) -> str:
    """
    Add items to the customer's shopping cart.
    Use this tool when the user wants to buy/add items.
    
    Args:
        items: A string listing items and quantities (e.g., "2x Headphones, 1x Watch").
        customer_phone: The customer's phone number (used as user ID).
        
    Returns:
        A confirmation message of what was added.
    """
    print(f"DEBUG: TOOL add_to_cart called. Items={items}, Phone={customer_phone}")
    from app.core.database import SessionLocal
    from app.models.models import Product, Cart, CartItem
    
    db = SessionLocal()
    try:
        # 1. Parse items (Resuse parsing logic)
        all_products = db.query(Product).filter(Product.isActive == True).all()
        
        # Simple parsing logic
        item_list = items.split(',')
        added_items_summary = []
        
        # Get or Create Cart
        cart = db.query(Cart).filter(Cart.user_phone == customer_phone).first()
        if not cart:
            cart = Cart(user_phone=customer_phone)
            db.add(cart)
            db.commit()
            db.refresh(cart)
        
        for item_text in item_list:
            qty = 1
            match = re.search(r'(\d+)\s*[xX]?\s*(.*)', item_text.strip())
            if match:
                try:
                    qty = int(match.group(1))
                    product_name_guess = match.group(2)
                except:
                    product_name_guess = item_text.strip()
            else:
                product_name_guess = item_text.strip()
            
            matched_product = None
            for p in all_products:
                if p.name.lower() in product_name_guess.lower() or product_name_guess.lower() in p.name.lower():
                    matched_product = p
                    break
            
            if matched_product:
                # Check if item already exists in cart, update quantity
                cart_item = db.query(CartItem).filter(CartItem.cart_id == cart.id, CartItem.product_id == matched_product.id).first()
                if cart_item:
                    cart_item.quantity += qty
                else:
                    cart_item = CartItem(cart_id=cart.id, product_id=matched_product.id, quantity=qty)
                    db.add(cart_item)
                
                added_items_summary.append(f"{qty}x {matched_product.name}")
        
        db.commit()
        
        if not added_items_summary:
            return "I couldn't identify the products to add. Please check product names."
        
        return f"Added to cart: {', '.join(added_items_summary)}. Type 'cart' to view your items or 'buy' to checkout."
        
    except Exception as e:
        print(f"ERROR in add_to_cart: {e}")
        return "Error adding to cart."
    finally:
        db.close()


@tool
def view_cart(customer_phone: str) -> str:
    """
    View the items currently in the customer's shopping cart.
    
    Args:
        customer_phone: The customer's phone number.
        
    Returns:
        A summary of the cart with total.
    """
    print(f"DEBUG: TOOL view_cart called. Phone={customer_phone}")
    from app.core.database import SessionLocal
    from app.models.models import Cart, CartItem
    
    db = SessionLocal()
    try:
        cart = db.query(Cart).filter(Cart.user_phone == customer_phone).first()
        if not cart or not cart.items:
            return "Your cart is empty."
        
        summary = "🛒 **Your Cart:**\n"
        total = 0
        for item in cart.items:
            line_total = item.quantity * item.product.price
            total += line_total
            summary += f"- {item.quantity}x {item.product.name}: ${line_total:.2f}\n"
        
        summary += f"\n**Total: ${total:.2f}**\n\nType 'buy' or 'checkout' to place your order."
        return summary
    except Exception as e:
        print(f"ERROR in view_cart: {e}")
        return "Error viewing cart."
    finally:
        db.close()
