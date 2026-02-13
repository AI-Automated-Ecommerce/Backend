from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import BusinessDetail
from app.schemas.schemas import BusinessDetailCreate, BusinessDetailUpdate, BusinessDetailResponse
from typing import List

router = APIRouter()

@router.get("/details", response_model=List[BusinessDetailResponse])
def get_business_details(db: Session = Depends(get_db)):
    """
    Get all business detail sections.
    """
    return db.query(BusinessDetail).all()

@router.post("/details", response_model=BusinessDetailResponse, status_code=status.HTTP_201_CREATED)
def create_business_detail(detail: BusinessDetailCreate, db: Session = Depends(get_db)):
    """
    Create a new business detail section.
    """
    db_detail = BusinessDetail(**detail.dict())
    db.add(db_detail)
    db.commit()
    db.refresh(db_detail)
    return db_detail

@router.put("/details/{detail_id}", response_model=BusinessDetailResponse)
def update_business_detail(detail_id: int, detail_in: BusinessDetailUpdate, db: Session = Depends(get_db)):
    """
    Update a business detail section.
    """
    db_detail = db.query(BusinessDetail).filter(BusinessDetail.id == detail_id).first()
    if not db_detail:
        raise HTTPException(status_code=404, detail="Business detail not found")
    
    update_data = detail_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_detail, field, value)
    
    db.commit()
    db.refresh(db_detail)
    return db_detail

@router.delete("/details/{detail_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_detail(detail_id: int, db: Session = Depends(get_db)):
    """
    Delete a business detail section.
    """
    db_detail = db.query(BusinessDetail).filter(BusinessDetail.id == detail_id).first()
    if not db_detail:
        raise HTTPException(status_code=404, detail="Business detail not found")
    
    db.delete(db_detail)
    db.commit()
    return None
