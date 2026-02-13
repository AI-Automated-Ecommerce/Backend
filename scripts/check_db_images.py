import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.models import Product

def check_products():
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        for p in products:
            print(f"Product: {p.name}, Image: {p.imageUrl}")
    finally:
        db.close()

if __name__ == "__main__":
    check_products()
