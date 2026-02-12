# Backend - AI Automated Business

The backend service for the AI Automated Business application, built with **FastAPI**. It handles API requests, database interactions, and integrates with the **Google Gemini API** for the AI Agent features.

## 🚀 Features

- **FastAPI Framework:** High-performance, easy-to-use Python web framework.
- **AI Agent Integration:** Powered by Google Gemini, capable of context-aware conversations.
- **Database Management:** Uses **SQLAlchemy** (sqlite by default) for product, order, and settings management.
- **API Endpoints:**
  - `/products`: Manage product catalog.
  - `/orders`: Place and track orders.
  - `/settings`: Configure business details.
  - `/chat`: Main chat interface.
  - `/whatsapp`: Webhooks for WhatsApp integration.
- **Admin Dashboard API:** Supports the frontend admin dashboard.

## 🛠 Prerequisites

- Python 3.9+
- Google Gemini API Key

## 📦 Setup & Installation

1. **Create a Virtual Environment**:

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2. **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

3. **Environment Variables**:
    Create a `.env` file in the `Backend` directory with the following:

    ```env
    GOOGLE_API_KEY=your_gemini_api_key
    DATABASE_URL=sqlite:///./sql_app.db
    ```

## 🏃‍♂️ Running the Server

Start the development server with auto-reload:

```bash
uvicorn app.main:app --reload
```

- The API will be available at `http://localhost:8000`.
- Interactive API docs (Swagger UI) at `http://localhost:8000/docs`.

## 📂 Key Files

- `app/main.py`: Entry point, app lifespan management (startup/shutdown).
- `app/services/ai_agent.py`: Implementation of the AI Agent logic.
- `app/api/endpoints/`: Directory containing all API route definitions.
- `app/core/database.py`: Database connection and session management.
