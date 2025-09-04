from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from ..models import UserCreate, UserLogin, UserResponse, Token
from ..database import get_supabase, get_password_hash, authenticate_user_optimized, register_user_optimized, check_user_exists
from ..auth import create_access_token, get_current_user, logout_user
from datetime import timedelta
from ..config import settings
import time
import hashlib
import json
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta

router = APIRouter(prefix="/auth", tags=["authentication"])

# Simple in-memory rate limiting (in production, use Redis or similar)
_registration_attempts: Dict[str, list] = defaultdict(list)
_max_attempts_per_hour = 5

# Cache for user profile responses with ETag support
_user_profile_cache: Dict[str, Dict] = {}
_cache_ttl = 300  # 5 minutes cache TTL

def check_rate_limit(client_ip: str) -> bool:   
    """
    Check if client has exceeded rate limit for registration attempts
    """
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    # Clean old attempts
    _registration_attempts[client_ip] = [
        attempt_time for attempt_time in _registration_attempts[client_ip]
        if attempt_time > hour_ago
    ]
    
    # Check if under limit
    if len(_registration_attempts[client_ip]) >= _max_attempts_per_hour:
        return False
    
    # Record this attempt
    _registration_attempts[client_ip].append(now)
    return True

def generate_etag(user_data: dict) -> str:
    """
    Generate ETag for user data to support conditional requests
    """
    # Create a hash of the user data for ETag
    data_string = json.dumps(user_data, sort_keys=True, default=str)
    return hashlib.md5(data_string.encode()).hexdigest()

def get_cached_user_profile(user_id: str) -> Optional[Dict]:
    """
    Get cached user profile if still valid
    """
    if user_id in _user_profile_cache:
        cache_entry = _user_profile_cache[user_id]
        if time.time() - cache_entry['timestamp'] < _cache_ttl:
            return cache_entry['data']
        else:
            # Remove expired cache entry
            del _user_profile_cache[user_id]
    return None

def cache_user_profile(user_id: str, user_data: dict, etag: str):
    """
    Cache user profile data with timestamp and ETag
    """
    _user_profile_cache[user_id] = {
        'data': user_data,
        'etag': etag,
        'timestamp': time.time()
    }

def clear_user_profile_cache(user_id: str = None):
    """
    Clear user profile cache (useful for profile updates)
    """
    if user_id:
        _user_profile_cache.pop(user_id, None)
    else:
        _user_profile_cache.clear()

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, request: Request):
    """
    Optimized user registration endpoint with improved performance:
    - Single database operation with conflict handling
    - Enhanced input validation
    - Rate limiting protection
    - Better error handling and security
    - Reduced response time
    """
    start_time = time.time()
    
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limit
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )
    
    try:
        # Use optimized registration function
        created_user = await register_user_optimized(
            email=user.email,
            password=user.password,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        if not created_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Log registration time for monitoring
        registration_time = (time.time() - start_time) * 1000
        print(f"Registration completed in {registration_time:.2f}ms for {user.email}")
        
        return UserResponse(
            id=created_user["id"],
            email=created_user["email"],
            first_name=created_user["first_name"],
            last_name=created_user["last_name"],
            created_at=created_user["created_at"],
            updated_at=created_user["updated_at"]
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the actual error for debugging (in production, use proper logging)
        print(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user. Please try again."
        )

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """
    Optimized login endpoint with improved performance:
    - Single database call for authentication
    - Async operations for better concurrency
    - Reduced response time
    """
    user = await authenticate_user_optimized(user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_user_profile(
    request: Request, 
    response: Response,
    current_user: dict = Depends(get_current_user)
):
    """
    Optimized user profile endpoint with caching and ETag support:
    - Response caching to reduce processing time
    - ETag support for conditional requests
    - Performance monitoring
    - Optimized data serialization
    """
    start_time = time.time()
    user_id = current_user["id"]
    
    # Check for ETag in request headers
    if_none_match = request.headers.get("if-none-match")
    
    # Try to get cached response first
    cached_data = get_cached_user_profile(user_id)
    
    if cached_data:
        cached_etag = cached_data.get('etag')
        
        # If client has the same ETag, return 304 Not Modified
        if if_none_match and if_none_match == cached_etag:
            response.status_code = 304
            return None
        
        # Return cached data with ETag
        response.headers["ETag"] = cached_etag
        response.headers["Cache-Control"] = "private, max-age=300"  # 5 minutes
        
        # Log performance
        processing_time = (time.time() - start_time) * 1000
        print(f"User profile served from cache in {processing_time:.2f}ms for user {user_id}")
        
        return cached_data['user_data']
    
    # Generate optimized user response
    user_response = {
        "id": current_user["id"],
        "email": current_user["email"],
        "first_name": current_user["first_name"],
        "last_name": current_user["last_name"],
        "created_at": current_user["created_at"],
        "updated_at": current_user["updated_at"]
    }
    
    # Generate ETag for the response
    etag = generate_etag(user_response)
    
    # Cache the response
    cache_user_profile(user_id, {
        'user_data': user_response,
        'etag': etag
    }, etag)
    
    # Set response headers
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=300"  # 5 minutes
    response.headers["Vary"] = "Authorization"
    
    # Log performance
    processing_time = (time.time() - start_time) * 1000
    print(f"User profile generated in {processing_time:.2f}ms for user {user_id}")
    
    return user_response

@router.get("/verify")
async def verify_token_validity(current_user: dict = Depends(get_current_user)):
    return {"valid": True, "user_id": current_user["id"]}

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout endpoint that clears user cache for security
    """
    await logout_user(current_user["email"])
    # Clear profile cache on logout
    clear_user_profile_cache(current_user["id"])
    return {"message": "Successfully logged out"}

@router.put("/me")
async def update_user_profile(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Update user profile endpoint that clears cache after updates
    """
    try:
        # Get update data from request body
        update_data = await request.json()
        
        # Validate allowed fields
        allowed_fields = ["first_name", "last_name"]
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not filtered_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        # Update user in database
        supabase = get_supabase()
        response = supabase.table("users").update(filtered_data).eq("id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile"
            )
        
        # Clear profile cache since data has changed
        clear_user_profile_cache(current_user["id"])
        
        return {"message": "Profile updated successfully", "updated_fields": list(filtered_data.keys())}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Profile update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile. Please try again."
        )
