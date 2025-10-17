from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings
from .database import get_supabase, verify_password, get_password_hash, get_user_by_email_cached, clear_user_cache
from .models import TokenData

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def verify_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
        return token_data
    except JWTError:
        raise credentials_exception

async def get_current_user_internal(credentials: HTTPAuthorizationCredentials = Depends(security), request: Request = None):
    """
    Internal function for get_current_user with domain validation
    """
    token = credentials.credentials
    token_data = verify_token(token)
    
    # Extract domain from request
    domain = request.headers.get("host") if request else None
    
    # Use cached user lookup instead of direct database call
    user = await get_user_by_email_cached(token_data.email, domain)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or invalid domain",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Public function for get_current_user that automatically includes domain validation
    """
    return await get_current_user_internal(credentials, request)

def get_domain_from_request(request: Request) -> str:
    """Helper function to extract domain from request headers"""
    return request.headers.get("host")

def authenticate_user(email: str, password: str, domain: str = None):
    """
    Legacy authenticate_user function - kept for backward compatibility
    Consider using authenticate_user_optimized for new implementations
    """
    supabase = get_supabase(domain)
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()
        if not response.data:
            return False
        
        user = response.data[0]
        if not verify_password(password, user["password"]):
            return False
        
        return user
    except Exception:
        return False

async def logout_user(email: str, domain: str = None):
    """
    Clear user cache on logout for security
    """
    clear_user_cache(email, domain)
