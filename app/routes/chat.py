from fastapi import APIRouter, Depends, HTTPException, status
from app.chat import create_session, call_openai, get_user_chat_sessions, delete_chat_session, get_chat_detail, get_session_info, check_question_scope
from app.auth import get_current_user
from ..models import ChatRequest, CreateSessionRequest, CreateSessionResponse, ChatSessionsListResponse, ChatDetailResponse, ScopeCheckRequest
from ..database import get_supabase

router = APIRouter(prefix="/chat", tags=["chatbot"])

@router.post("/scope-check")
def scope_check_endpoint(req: ScopeCheckRequest):
    """Check if a user question is within the allowed scope for getOrdersOverTime function only"""
    try:
        scope_result = check_question_scope(req.message)
        return scope_result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check question scope"
        )

@router.get("/sessions", response_model=ChatSessionsListResponse)
def get_chat_sessions(
    page: int = 1, 
    pagination: int = 10, 
    current_user: dict = Depends(get_current_user)
):
    """Get paginated chat sessions for the authenticated user"""
    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if pagination < 1 or pagination > 100:
            pagination = 10
        
        # Get the authenticated user's ID
        supabase = get_supabase()
        response = supabase.table("users").select("id").eq("email", current_user["email"]).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        user_id = response.data[0]["id"]
        
        # Get paginated chat sessions for this user
        result = get_user_chat_sessions(user_id, page, pagination)
        
        return ChatSessionsListResponse(
            user_id=user_id,
            sessions=result["sessions"],
            total_sessions=result["total_sessions"],
            page=result["page"],
            pagination=result["pagination"],
            total_pages=result["total_pages"],
            has_next=result["has_next"],
            has_prev=result["has_prev"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat sessions"
        )

@router.delete("/sessions/{session_id}")
def delete_chat_session_endpoint(session_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a specific chat session and all its messages - requires authentication"""
    try:
        # Get the authenticated user's ID
        supabase = get_supabase()
        response = supabase.table("users").select("id").eq("email", current_user["email"]).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        user_id = response.data[0]["id"]
        
        # Delete the session (function handles ownership verification)
        delete_chat_session(session_id, user_id)
        
        return {"message": "Chat session deleted successfully", "session_id": session_id}
        
    except ValueError as e:
        # Handle specific validation errors
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        elif "only delete your own" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own chat sessions"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat session"
        )

@router.post("/create_chat", response_model=CreateSessionResponse)
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
        return CreateSessionResponse(
            session_id=session["id"],
            user_id=session["user_id"],
            title=session["title"],
            created_at=session["created_at"]
        )
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
            "description": "Visualize order volume trends over time. Helps detect growth, spikes, or drop-offs. Use this when users ask about order trends, growth patterns, or time-based order analytics.",
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

@router.get("/sessions/{session_id}/info")
def get_session_info_endpoint(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get basic session information including updated title"""
    try:
        # Get the authenticated user's ID
        supabase = get_supabase()
        response = supabase.table("users").select("id").eq("email", current_user["email"]).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        user_id = response.data[0]["id"]
        
        # Get session info (function handles ownership verification)
        session_info = get_session_info(session_id)
        
        # Verify ownership
        if session_info["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own chat sessions"
            )
        
        return {
            "session_id": session_info["id"],
            "title": session_info["title"],
            "created_at": session_info["created_at"],
            "user_id": session_info["user_id"]
        }
        
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session info"
        )

@router.get("/sessions/{session_id}/detail", response_model=ChatDetailResponse)
def get_chat_detail_endpoint(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed chat information including all messages for a specific session"""
    try:
        # Get the authenticated user's ID
        supabase = get_supabase()
        response = supabase.table("users").select("id").eq("email", current_user["email"]).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        user_id = response.data[0]["id"]
        
        # Get chat detail (function handles ownership verification)
        chat_detail = get_chat_detail(session_id, user_id)
        
        return ChatDetailResponse(**chat_detail)
        
    except ValueError as e:
        # Handle specific validation errors
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        elif "only view your own" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own chat sessions"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat detail"
        )


