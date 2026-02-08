from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Product, Category
from app.schemas.schemas import ProductCreate, ProductUpdate

router = APIRouter()

@router.get("/products")
def get_products(db: Session = Depends(get_db)):
    """
    List all available products.
    """
    products = db.query(Product).filter(Product.isActive == True).all()
    return products

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """
    List all available categories.
    """
    categories = db.query(Category).all()
    return categories

@router.post("/products")
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(
        name=product.name,
        description=product.description,
        price=product.price,
        stockQuantity=product.stockQuantity,
        categoryId=product.categoryId,
        imageUrl=product.imageUrl
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.put("/products/{product_id}")
def update_product(product_id: int, product: ProductUpdate, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product

@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
         raise HTTPException(status_code=404, detail="Product not found")
    
    # Check dependencies (e.g. order items) if needed, or set isActive=False
    # For now, let's just Soft Delete
    db_product.isActive = False
    db.commit()
    return {"status": "deleted"}
