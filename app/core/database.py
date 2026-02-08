from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Get database URL from environment variable
# Defaults to SQLite for local development if not set
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./ecommerce.db"
)

# Configure engine based on database type
if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL configuration with connection pooling
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,          # Number of connections to maintain
        max_overflow=20,       # Max additional connections when pool is full
        pool_pre_ping=True,    # Verify connections before using
        pool_recycle=3600,     # Recycle connections after 1 hour
        echo=False             # Set to True for SQL query logging
    )
else:
    # SQLite configuration (local development)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    Automatically closes session after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
