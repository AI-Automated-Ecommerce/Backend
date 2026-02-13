#!/usr/bin/env python3
"""
Migration script to add PAYMENT_REVIEW_REQUESTED to OrderStatus enum.

This script adds the missing enum value to the PostgreSQL enum type.
Run this script before using the updated OrderStatus enum:
    python scripts/migrate_add_payment_review_status.py
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from sqlalchemy import text

load_dotenv()

def migrate():
    """Add PAYMENT_REVIEW_REQUESTED to OrderStatus enum if it doesn't exist."""
    
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ecommerce.db")
    
    if not DATABASE_URL.startswith("postgresql"):
        print("This migration is only for PostgreSQL databases.")
        return
        
    with engine.connect() as connection:
        # Check if enum value already exists
        result = connection.execute(text("""
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'PAYMENT_REVIEW_REQUESTED' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'orderstatus');
        """))
        
        if result.fetchone():
            print("✓ 'PAYMENT_REVIEW_REQUESTED' enum value already exists. No migration needed.")
            return
        
        print("Adding 'PAYMENT_REVIEW_REQUESTED' to OrderStatus enum...")
        
        # Add the new enum value
        connection.execute(text("""
            ALTER TYPE orderstatus ADD VALUE 'PAYMENT_REVIEW_REQUESTED';
        """))
        connection.commit()
        
        print("✓ Successfully added 'PAYMENT_REVIEW_REQUESTED' to OrderStatus enum")

if __name__ == "__main__":
    try:
        migrate()
        print("\n✓ Enum migration completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Enum migration failed: {str(e)}")
        sys.exit(1)