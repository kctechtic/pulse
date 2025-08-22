from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from ..models import (
    ChatRequest, ChatResponse, ChatSession, ChatSessionCreate, 
    ChatSessionUpdate, ChatSessionResponse
)
from ..chat_service import chat_service
from ..auth import get_current_user
from ..database import get_supabase_client

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/send", response_model=ChatResponse)
async def send_message(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send a chat message and get AI response"""
    try:
        # Extract user_id from the current_user dict (from your custom users table)
        user_id = current_user["id"]
        response = await chat_service.process_chat_message(chat_request, user_id)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat message: {str(e)}"
        )

@router.post("/sessions", response_model=ChatSession)
async def create_session(
    session_data: ChatSessionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new chat session"""
    try:
        user_id = current_user["id"]
        session = await chat_service.create_chat_session(
            user_id=user_id,
            title=session_data.title,
            system_prompt=session_data.system_prompt
        )
        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat session: {str(e)}"
        )

@router.get("/sessions", response_model=List[ChatSession])
async def get_sessions(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all chat sessions for the current user"""
    try:
        user_id = current_user["id"]
        sessions = await chat_service.get_user_sessions(user_id, limit)
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat sessions: {str(e)}"
        )

@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific chat session with all messages"""
    try:
        user_id = current_user["id"]
        session = await chat_service.get_chat_session(session_id, user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat session: {str(e)}"
        )

@router.put("/sessions/{session_id}", response_model=ChatSession)
async def update_session(
    session_id: str,
    session_update: ChatSessionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a chat session"""
    try:
        user_id = current_user["id"]
        # Use model_dump for Pydantic v2 or dict for v1
        try:
            updates = session_update.model_dump(exclude_unset=True)
        except AttributeError:
            updates = session_update.dict(exclude_unset=True)
        session = await chat_service.update_session(session_id, user_id, updates)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update chat session: {str(e)}"
        )

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a chat session (soft delete)"""
    try:
        user_id = current_user["id"]
        success = await chat_service.delete_session(session_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        return {"message": "Chat session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chat session: {str(e)}"
        )

@router.post("/sessions/{session_id}/clear")
async def clear_session_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Clear all messages from a chat session (keep the session)"""
    try:
        user_id = current_user["id"]
        # Get session to verify ownership
        session = await chat_service.get_chat_session(session_id, user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        # Delete all messages for this session
        supabase = get_supabase_client()
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        
        return {"message": "Chat session messages cleared successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear chat session messages: {str(e)}"
        )
