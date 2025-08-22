import httpx
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from .models import ChatMessage, MessageRole, ChatSession, ChatRequest, ChatResponse
from .database import get_supabase_client
from .config import settings

class ChatService:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.edge_function_url = settings.edge_function_url
        
    async def create_chat_session(self, user_id: str, title: str = None, system_prompt: str = None) -> ChatSession:
        """Create a new chat session for a user"""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        session_data = {
            "id": session_id,
            "user_id": user_id,
            "title": title or f"Chat {now.strftime('%Y-%m-%d %H:%M')}",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "is_active": True,
            "metadata": {
                "system_prompt": system_prompt,
                "message_count": 0
            }
        }
        
        # Store in Supabase
        result = self.supabase.table("chat_sessions").insert(session_data).execute()
        
        return ChatSession(**session_data)
    
    async def get_chat_session(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """Retrieve a chat session with its messages"""
        # Get session
        session_result = self.supabase.table("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).execute()
        
        if not session_result.data:
            return None
            
        session_data = session_result.data[0]
        
        # Get messages for this session
        messages_result = self.supabase.table("chat_messages").select("*").eq("session_id", session_id).order("timestamp", desc=False).execute()
        
        messages = []
        for msg_data in messages_result.data:
            messages.append(ChatMessage(**msg_data))
        
        session = ChatSession(**session_data)
        session.messages = messages
        
        return session
    
    async def get_user_sessions(self, user_id: str, limit: int = 20) -> List[ChatSession]:
        """Get all chat sessions for a user"""
        result = self.supabase.table("chat_sessions").select("*").eq("user_id", user_id).eq("is_active", True).order("updated_at", desc=True).limit(limit).execute()
        
        sessions = []
        for session_data in result.data:
            sessions.append(ChatSession(**session_data))
            
        return sessions
    
    async def add_message(self, session_id: str, role: MessageRole, content: str, metadata: Dict[str, Any] = None) -> ChatMessage:
        """Add a message to a chat session"""
        message_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        message_data = {
            "id": message_id,
            "session_id": session_id,
            "role": role.value,
            "content": content,
            "timestamp": now.isoformat(),
            "metadata": metadata or {}
        }
        
        # Store message in Supabase
        result = self.supabase.table("chat_messages").insert(message_data).execute()
        
        # Update session timestamp
        self.supabase.table("chat_sessions").update({"updated_at": now.isoformat()}).eq("id", session_id).execute()
        
        return ChatMessage(**message_data)
    
    async def process_chat_message(self, chat_request: ChatRequest, user_id: str) -> ChatResponse:
        """Process a chat message and get response from edge function"""
        
        # Create or get existing session
        if chat_request.session_id:
            session = await self.get_chat_session(chat_request.session_id, user_id)
            if not session:
                raise ValueError("Session not found or access denied")
        else:
            # Create new session
            session = await self.create_chat_session(
                user_id=user_id,
                title=chat_request.message[:50] + "..." if len(chat_request.message) > 50 else chat_request.message,
                system_prompt=chat_request.system_prompt
            )
        
        # Add user message to session
        user_message = await self.add_message(
            session_id=session.id,
            role=MessageRole.USER,
            content=chat_request.message
        )
        
        # Prepare conversation context for edge function
        conversation_context = await self._prepare_conversation_context(session.id, chat_request)
        
        # Call Supabase edge function
        assistant_response = await self._call_edge_function(conversation_context, chat_request)
        
        # Add assistant response to session
        assistant_message = await self.add_message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=assistant_response,
            metadata={"model_response": True}
        )
        
        return ChatResponse(
            response=assistant_response,
            session_id=session.id,
            message_id=assistant_message.id,
            timestamp=datetime.utcnow(),
            metadata={"user_message_id": user_message.id}
        )
    
    async def _prepare_conversation_context(self, session_id: str, chat_request: ChatRequest) -> Dict[str, Any]:
        """Prepare conversation context for the edge function"""
        # Get recent messages for context (last N messages based on config)
        max_messages = settings.max_context_messages
        messages_result = self.supabase.table("chat_messages").select("*").eq("session_id", session_id).order("timestamp", desc=True).limit(max_messages).execute()
        
        messages = []
        for msg_data in reversed(messages_result.data):  # Reverse to get chronological order
            messages.append({
                "role": msg_data["role"],
                "content": msg_data["content"]
            })
        
        return {
            "messages": messages,
            "system_prompt": chat_request.system_prompt,
            "temperature": chat_request.temperature or settings.default_temperature,
            "max_tokens": chat_request.max_tokens or settings.default_max_tokens
        }
    
    async def _call_edge_function(self, conversation_context: Dict[str, Any], chat_request: ChatRequest) -> str:
        """Call the Supabase edge function to get AI response"""
        if not self.edge_function_url:
            return "Error: Edge function URL not configured. Please set EDGE_FUNCTION_URL in your environment."
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.edge_function_url,
                    json=conversation_context,
                    headers={
                        "Authorization": f"Bearer {self.supabase.supabase_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=settings.chat_timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "I apologize, but I couldn't generate a response.")
                else:
                    return f"Error: {response.status_code} - {response.text}"
                    
            except Exception as e:
                return f"I apologize, but I encountered an error: {str(e)}"
    
    async def update_session(self, session_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[ChatSession]:
        """Update a chat session"""
        # Verify ownership
        session = await self.get_chat_session(session_id, user_id)
        if not session:
            return None
        
        # Update session
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = self.supabase.table("chat_sessions").update(updates).eq("id", session_id).eq("user_id", user_id).execute()
        
        if result.data:
            return ChatSession(**result.data[0])
        return None
    
    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Soft delete a chat session"""
        # Verify ownership
        session = await self.get_chat_session(session_id, user_id)
        if not session:
            return False
        
        # Soft delete by setting is_active to False
        result = self.supabase.table("chat_sessions").update({"is_active": False}).eq("id", session_id).eq("user_id", user_id).execute()
        
        return bool(result.data)

# Global instance
chat_service = ChatService()
