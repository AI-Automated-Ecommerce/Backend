from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.api.endpoints import products, orders, admin, chat, whatsapp
from scripts.seed import seed_data

# Create tables (ensure DB matches models)
# In production, use Alembic migrations instead of create_all
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Handles startup and shutdown tasks.
    """
    # Startup tasks
    print("=" * 60)
    print("🚀 Starting E-commerce AI Service...")
    print("=" * 60)
    
    # Seed database
    print("📦 Seeding database...")
    seed_data()
    print("✅ Database seeded")
    
    # Initialize AI Agent
    print("🤖 Initializing AI Agent...")
    from app.services.ai_agent import agent
    
    # Verify AI agent configuration
    if agent.client:
        print("✅ AI Agent initialized with Google Gemini API")
        print(f"   Model: gemini-2.0-flash-exp")
        print(f"   Security: Restricted to {agent.ALLOWED_TABLES}")
    else:
        print("⚠️  AI Agent initialized (Mock mode - no Gemini API key)")
        print("   Set GOOGLE_API_KEY in .env for full AI functionality")
    
    print("=" * 60)
    print("✅ Server ready!")
    print("=" * 60)
    
    yield
    
    # Shutdown tasks
    print("\n" + "=" * 60)
    print("👋 Shutting down E-commerce AI Service...")
    print("=" * 60)

app = FastAPI(title="AI E-commerce Service", lifespan=lifespan)

# --- CORS Configuration ---
origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://localhost:5173", # Vite default
    "https://frontend-0bfs.onrender.com",
    "https://frontend-0bfs.onrender.com/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "E-commerce AI Agent"}

# Include Routers
app.include_router(products.router, tags=["Products"])
app.include_router(orders.router, tags=["Orders"])
app.include_router(admin.router, tags=["Admin"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(whatsapp.router, tags=["WhatsApp"])
