import re
from langchain_core.tools import tool
from app.core.database import SessionLocal
from app.models.models import Product, Cart, CartItem, Order, OrderItem, OrderStatus, BusinessSettings

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

@tool
def generate_invoice(customer_name: str, customer_address: str, customer_phone: str) -> str:
    """
    Generate an invoice for the customer's order based on their CART.
    
    Args:
        customer_name: Name of the customer.
        customer_address: Delivery address.
        customer_phone: Contact phone number.
    
    Returns:
        An invoice summary string.
    """
    print(f"DEBUG: TOOL generate_invoice called. Name={customer_name}, Phone={customer_phone}")
    
    db = SessionLocal()
    try:
        # 1. Fetch Cart
        cart = db.query(Cart).filter(Cart.user_phone == customer_phone).first()
        
        if not cart or not cart.items:
            return "Your cart is empty! Please add items before checking out."

        order_items = []
        total_amount = 0
        found_products_summary = []
        
        for cart_item in cart.items:
            order_items.append({
                "product": cart_item.product,
                "quantity": cart_item.quantity,
                "price": cart_item.product.price
            })
            total_amount += (cart_item.product.price * cart_item.quantity)
            found_products_summary.append(f"{cart_item.quantity}x {cart_item.product.name} (@ ${cart_item.product.price})")
        
        # 2. Create Order (Pending)
        new_order = Order(
            customerName=customer_name,
            customerPhone=customer_phone,
            shippingAddress=customer_address,
            paymentMethod="Bank Transfer",
            status=OrderStatus.PENDING,
            totalAmount=total_amount, 
            customerEmail="" 
        )
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        
        # 3. Create OrderItems
        for item in order_items:
            db_item = OrderItem(
                orderId=new_order.id,
                productId=item["product"].id,
                quantity=item["quantity"],
                unitPrice=item["price"]
            )
            db.add(db_item)
        db.commit()
        
        # 4. Return Invoice Summary (NO Payment Details yet)
        summary_str = "\n".join(found_products_summary)
        return (f"📄 **INVOICE GENERATED** (Order #{new_order.id})\n\n"
                f"**Customer:** {customer_name}\n"
                f"**Address:** {customer_address}\n"
                f"**Items:**\n{summary_str}\n\n"
                f"**Total Amount:** ${total_amount:.2f}\n\n"
                f"Please CONFIRM this invoice if details are correct. Once confirmed, I will provide payment details.")
        
    except Exception as e:
        print(f"ERROR in generate_invoice: {e}")
        import traceback
        traceback.print_exc()
        return "Error generating invoice. Please try again."
    finally:
        db.close()

@tool
def get_payment_details(customer_phone: str) -> str:
    """
    Get the bank payment details for the business.
    Use this tool ONLY after the user has confirmed the invoice and is ready to pay.
    This also clears the user's cart.
    
    Args:
        customer_phone: The customer's phone number.
    """
    print("DEBUG: TOOL get_payment_details called")
    
    db = SessionLocal()
    try:
        settings = db.query(BusinessSettings).first()
        if not settings or not settings.bank_details:
            return "Bank details are not currently configured. Please contact support."
        
        # Clear Cart (cascade will delete CartItems automatically)
        cart = db.query(Cart).filter(Cart.user_phone == customer_phone).first()
        if cart:
            db.delete(cart)
            db.commit()
        
        return f"Please transfer the amount to the following bank account:\n\n{settings.bank_details}\n\nOnce paid, please send a slip/screenshot here for manual verification."
    finally:
        db.close()

@tool
def confirm_user_payment(customer_phone: str, transaction_ref: str = None) -> str:
    """
    Confirm that the user has made a payment for their pending order.
    Use this tool when the user says they have paid, transferred the money, or sends a slip.
    This updates the order status to 'PAYMENT_REVIEW_REQUESTED' so the admin can verify it.
    
    Args:
        customer_phone: The customer's phone number.
        transaction_ref: (Optional) The transaction reference number or slip details if provided by the user.
    """
    print(f"DEBUG: TOOL confirm_user_payment called. Phone={customer_phone}, Ref={transaction_ref}")
    
    db = SessionLocal()
    try:
        # Find the most recent PENDING order for this user
        order = db.query(Order).filter(
            Order.customerPhone == customer_phone,
            Order.status == OrderStatus.PENDING
        ).order_by(Order.createdAt.desc()).first()
        
        if not order:
            return "I couldn't find a pending order for your number. Please make sure you have generated an invoice first."
        
        # Update status
        order.status = OrderStatus.PAYMENT_REVIEW_REQUESTED
        if transaction_ref:
            order.paymentRef = transaction_ref
            
        db.commit()
        
        return (f"Thank you! I have marked your order #{order.id} as PAID/REVIEW REQUESTED.\n"
                f"Our team will verify the payment and ship your items soon.\n"
                f"You will receive a confirmation once verified.")
    except Exception as e:
        print(f"ERROR in confirm_user_payment: {e}")
        return "An error occurred while updating your payment status. Please try again or contact support."
    finally:
        db.close()
