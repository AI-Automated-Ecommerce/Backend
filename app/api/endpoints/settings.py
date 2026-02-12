from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import BusinessSettings
from app.schemas.schemas import BusinessSettingsCreate, BusinessSettingsUpdate, BusinessSettingsResponse

router = APIRouter()

@router.get("/settings", response_model=BusinessSettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    """
    Get the business settings.
    If no settings exist, returns a default empty object.
    """
    settings = db.query(BusinessSettings).first()
    if not settings:
        # Create default settings if none exist
        settings = BusinessSettings(business_name="My Business")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@router.put("/settings", response_model=BusinessSettingsResponse)
def update_settings(settings_in: BusinessSettingsUpdate, db: Session = Depends(get_db)):
    """
    Update the business settings.
    """
    settings = db.query(BusinessSettings).first()
    if not settings:
        settings = BusinessSettings(**settings_in.dict())
        db.add(settings)
    else:
        update_data = settings_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)
    
    db.commit()
    db.refresh(settings)
    return settings
