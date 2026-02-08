import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import Product, Category

def seed_data():
    db = SessionLocal()
    try:
        # Check if categories already exist
        if db.query(Category).count() > 0:
            print("Database already contains data. Skipping seed.")
            return

        print("Seeding database...")
        
        # 1. Create Categories
        electronics = Category(name="Electronics", description="Gadgets and devices")
        accessories = Category(name="Accessories", description="Computer peripherals")
        home = Category(name="Home", description="Home appliances")
        
        db.add_all([electronics, accessories, home])
        db.commit()
        
        # Refresh to get IDs
        db.refresh(electronics)
        db.refresh(accessories)
        db.refresh(home)
        
        # 2. Create Products
        products = [
            Product(
                name="Wireless Headphones", 
                description="Noise cancelling over-ear headphones with 20h battery life.", 
                price=99.99, 
                stockQuantity=50,
                categoryId=electronics.id,
                imageUrl="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=300"
            ),
            Product(
                name="Smart Watch", 
                description="Fitness tracker with heart rate monitor and GPS.", 
                price=149.50, 
                stockQuantity=30,
                categoryId=electronics.id,
                imageUrl="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300"
            ),
            Product(
                name="Mechanical Keyboard", 
                description="RGB Backlit mechanical keyboard with Blue switches.", 
                price=75.00, 
                stockQuantity=20,
                categoryId=accessories.id,
                imageUrl="https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=300"
            ),
            Product(
                name="Gaming Mouse", 
                description="High precision 16000 DPI gaming mouse.", 
                price=45.99, 
                stockQuantity=40,
                categoryId=accessories.id,
                imageUrl="https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=300"
            ),
            Product(
                name="Coffee Maker", 
                description="Programmable drip coffee maker 12-cup capacity.", 
                price=39.99, 
                stockQuantity=15,
                categoryId=home.id,
                imageUrl="https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=300"
            )
        ]
        db.add_all(products)
        db.commit()
        print("Seeding complete.")
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
