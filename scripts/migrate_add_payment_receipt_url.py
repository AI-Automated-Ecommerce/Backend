#!/usr/bin/env python3
"""
Migration script to add paymentReceiptUrl column to Order table.

This script handles both PostgreSQL and SQLite databases.
Run this script before starting the application:
    python scripts/migrate_add_payment_receipt_url.py
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, SessionLocal
from sqlalchemy import text, inspect

load_dotenv()

def column_exists(connection, table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(connection)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def migrate():
    """Add paymentReceiptUrl column to Order table if it doesn't exist."""
    
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ecommerce.db")
    
    with engine.connect() as connection:
        # Check if column already exists
        if column_exists(connection, 'Order', 'paymentReceiptUrl'):
            print("✓ Column 'paymentReceiptUrl' already exists in Order table. No migration needed.")
            return
        
        print("Adding 'paymentReceiptUrl' column to Order table...")
        
        # Add the column
        if DATABASE_URL.startswith("postgresql"):
            # PostgreSQL syntax
            sql = text("""
                ALTER TABLE "Order"
                ADD COLUMN "paymentReceiptUrl" VARCHAR(500) NULL;
            """)
        else:
            # SQLite syntax
            sql = text("""
                ALTER TABLE "Order"
                ADD COLUMN "paymentReceiptUrl" VARCHAR(500);
            """)
        
        connection.execute(sql)
        connection.commit()
        print("✓ Successfully added 'paymentReceiptUrl' column to Order table")

if __name__ == "__main__":
    try:
        migrate()
        print("\n✓ Migration completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        sys.exit(1)
