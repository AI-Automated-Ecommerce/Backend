from langchain_core.tools import tool


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
    from app.core.database import SessionLocal
    from app.models.models import Order, OrderItem, Product, OrderStatus, Cart
    
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
