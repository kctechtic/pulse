from fastapi import APIRouter, Depends, HTTPException, status
from app.chat import create_session, call_openai
from app.auth import get_current_user
from ..models import ChatRequest, CreateSessionRequest
from ..database import get_supabase

router = APIRouter(prefix="/chat", tags=["chatbot"])

@router.post("/create_chat")
def create_chat(req: CreateSessionRequest, current_user: dict = Depends(get_current_user)):
    """Create a new chat session - requires authentication"""
    # Verify the user_id matches the authenticated user
    supabase = get_supabase()
    try:
        response = supabase.table("users").select("id").eq("email", current_user["email"]).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        authenticated_user_id = response.data[0]["id"]
        
        if req.user_id != authenticated_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID mismatch - you can only create sessions for yourself"
            )
        
        session = create_session(req.user_id, req.title)
        return {"session_id": session["id"]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )

tools = [
    {
        "type": "function",
        "function": {
            "name": "getOrdersOverTime",
            "description": "Returns revenue trends grouped by daily, weekly, or monthly interval. Use this when users ask about revenue trends, order patterns over time, or need time-based analytics. IMPORTANT: Always use current dates for relative time references.",
            "parameters": {
                "type": "object",
                "properties": {
                    "interval": {
                        "type": "string",
                        "enum": ["day", "week", "month"],
                        "description": "Time grouping interval. Choose 'day' for daily trends, 'week' for weekly patterns, or 'month' for monthly overview. Analyze the user's request to determine the most appropriate interval."
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date in YYYY-MM-DD format. For relative time references (e.g., 'last week', 'past 2 weeks'), calculate from TODAY's current date. CRITICAL: Always use current year (2025) unless explicitly requested otherwise. Never use dates from 2023 or earlier."
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in YYYY-MM-DD format. For relative time references, this is typically TODAY's date. For specific periods, use the end date mentioned in the user's request. CRITICAL: Always use the current year (2025) unless explicitly requested otherwise."
                    },
                    "currency": {
                        "type": "string",
                        "description": "Currency to filter revenue data (e.g., 'USD', 'EUR'). Include this only if the user specifically mentions a currency."
                    }
                },
                "required": ["interval", "start_date", "end_date"]
            }
        }
    }
]

@router.post("/chat")
def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Send a chat message - requires authentication"""
    # Verify the user_id matches the authenticated user
    supabase = get_supabase()
    try:
        response = supabase.table("users").select("id").eq("email", current_user["email"]).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        authenticated_user_id = response.data[0]["id"]
        
        if req.user_id != authenticated_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID mismatch - you can only send messages for yourself"
            )
        
        answer = call_openai(req.message, tools, req.session_id, req.user_id)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message"
        )
