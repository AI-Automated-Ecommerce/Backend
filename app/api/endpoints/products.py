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
    
    # Check dependencies (e.g. order items)
    # We can rely on database integrity error, or check manually.
    # checking manually gives better error message
    from app.models.models import OrderItem
    dependencies = db.query(OrderItem).filter(OrderItem.productId == product_id).first()
    if dependencies:
        # Fallback to soft delete or error?
        # User requested delete api, usually implies hard delete or at least "gone from view"
        # If we can't hard delete, we should probably tell them why, OR soft delete.
        # Let's try to return an error first as per plan.
        raise HTTPException(status_code=400, detail="Cannot delete product because it is part of existing orders.")

    try:
        print(f"--- HARD DELETING PRODUCT {product_id} ---")
        db.delete(db_product)
        db.commit()
        print(f"--- DELETED PRODUCT {product_id} ---")
    except Exception as e:
        print(f"--- DELETE FAILED: {e} ---")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete product: {str(e)}")
    
    return {"status": "deleted"}
