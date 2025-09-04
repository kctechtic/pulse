from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional
from datetime import datetime
import re

class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        """Validate name fields"""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        if not re.match(r'^[a-zA-Z\s\-\.]+$', v):
            raise ValueError('Name can only contain letters, spaces, hyphens, and periods')
        return v.strip()
    
    @validator('email')
    def validate_email_domain(cls, v):
        """Basic email domain validation"""
        # Additional validation beyond EmailStr
        if v and '@' in v:
            domain = v.split('@')[1]
            if len(domain) < 3:
                raise ValueError('Invalid email domain')
        return v

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

class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: datetime

class ScopeCheckRequest(BaseModel):
    message: str

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