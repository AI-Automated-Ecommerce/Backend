import sys
import os

# Ensure the parent directory is in the path so we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.models import BusinessDetail

def seed_business_details():
    db = SessionLocal()
    try:
        print("Seeding Business Details...")
        
        # Check if details already exist to avoid duplicates
        existing_count = db.query(BusinessDetail).count()
        if existing_count > 0:
            print(f"Database already contains {existing_count} business details. Skipping.")
            return

        details = [
            BusinessDetail(
                title="About Us",
                content="We are a premium e-commerce store dedicated to providing high-quality electronics and accessories. \n\nFounded in 2023, our mission is to make technology accessible and affordable for everyone. We pride ourselves on excellent customer service and fast shipping."
            ),
            BusinessDetail(
                title="Our Services",
                content="1. **Product Sales**: Wide range of electronics including headphones, smartwatches, and computer accessories.\n2. **Fast Delivery**: We ship within 24 hours of order confirmation.\n3. **Tech Support**: Free technical support for all products purchased from us.\n4. **Warranty Claims**: We handle warranty claims directly with manufacturers."
            ),
            BusinessDetail(
                title="Pricing & Payments",
                content="We offer competitive pricing on all our products.\n\n- **Standard Shipping**: $5.00 (Free for orders over $50)\n- **Express Shipping**: $15.00\n\n**Payment Methods**:\n- Bank Transfer\n- Cash on Delivery (available for select locations)\n- Credit/Debit Card (Coming Soon)"
            ),
            BusinessDetail(
                title="Return Policy",
                content="We accept returns within 30 days of purchase.\n\n- Items must be in original condition.\n- Return shipping is covered by the customer unless the item is defective.\n- Refunds are processed within 5-7 business days."
            )
        ]

        db.add_all(details)
        db.commit()
        print("Successfully added sample business details!")
        
    except Exception as e:
        print(f"Error seeding business details: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_business_details()
