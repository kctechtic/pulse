from supabase import create_client, Client
from .config import settings
from passlib.context import CryptContext
from functools import lru_cache
import asyncio
from typing import Optional, Dict, Any

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Supabase client with connection pooling
@lru_cache(maxsize=1)
def get_supabase() -> Client:
    return create_client(
        settings.supabase_url, 
        settings.supabase_anon_key
    )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Optimized user authentication with single database call
async def authenticate_user_optimized(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Optimized authentication that returns user data in a single database call
    """
    supabase = get_supabase()
    try:
        # Single database call to get user with password verification
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        if not response.data:
            return None
        
        user = response.data[0]
        
        # Verify password
        if not verify_password(password, user["password"]):
            return None
        
        # Remove password from returned user data for security
        user.pop("password", None)
        return user
        
    except Exception:
        return None

# Cache for user data to reduce database calls
_user_cache: Dict[str, Dict[str, Any]] = {}

async def get_user_by_email_cached(email: str) -> Optional[Dict[str, Any]]:
    """
    Get user by email with caching to reduce database calls
    """
    # Check cache first
    if email in _user_cache:
        return _user_cache[email]
    
    supabase = get_supabase()
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        if not response.data:
            return None
        
        user = response.data[0]
        # Remove password from cached data
        user.pop("password", None)
        
        # Cache the user data
        _user_cache[email] = user
        
        return user
        
    except Exception:
        return None

def clear_user_cache(email: str = None):
    """
    Clear user cache - useful for logout or profile updates
    """
    if email:
        _user_cache.pop(email, None)
    else:
        _user_cache.clear()

# Optimized user registration with single database operation
async def register_user_optimized(email: str, password: str, first_name: str, last_name: str) -> Optional[Dict[str, Any]]:
    """
    Optimized user registration that uses a single database operation with conflict handling
    """
    supabase = get_supabase()
    hashed_password = get_password_hash(password)
    
    try:
        # Use upsert with conflict resolution to handle race conditions
        new_user = {
            "email": email,
            "password": hashed_password,
            "first_name": first_name,
            "last_name": last_name
        }
        
        # Insert with conflict detection
        response = supabase.table("users").insert(new_user).execute()
        
        if not response.data:
            return None
        
        created_user = response.data[0]
        # Remove password from returned data
        created_user.pop("password", None)
        
        return created_user
        
    except Exception as e:
        # Check if it's a unique constraint violation (email already exists)
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            return None  # User already exists
        raise e

async def check_user_exists(email: str) -> bool:
    """
    Fast check if user exists without fetching full user data
    """
    supabase = get_supabase()
    try:
        # Only select id to minimize data transfer
        response = supabase.table("users").select("id").eq("email", email).limit(1).execute()
        return len(response.data) > 0
    except Exception:
        return False
