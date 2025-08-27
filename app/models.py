from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

class CreateSessionRequest(BaseModel):
    user_id: str
    title: Optional[str] = None

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    message_count: int
    last_message: str
    last_message_time: Optional[datetime] = None

class ChatSessionsListResponse(BaseModel):
    user_id: str
    sessions: list[ChatSessionResponse]
    total_sessions: int
    page: int
    pagination: int
    total_pages: int
    has_next: bool
    has_prev: bool

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    session_id: str

class ChatDetailResponse(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    user_id: str
    messages: list[ChatMessageResponse]
    total_messages: int