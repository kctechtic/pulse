from supabase import create_client, Client
from .config import settings, get_supabase_config
from passlib.context import CryptContext
from functools import lru_cache
import asyncio
from typing import Optional, Dict, Any

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Supabase client with connection pooling
@lru_cache(maxsize=10)  # Increased cache size for multiple domains
def get_supabase(domain: str = None) -> Client:
    """
    Get Supabase client for a specific domain.
    Uses domain-based configuration to connect to the appropriate Supabase project.
    """
    config = get_supabase_config(domain)
    return create_client(
        config["project_url"], 
        config["api_key"]
    )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Optimized user authentication with single database call
async def authenticate_user_optimized(email: str, password: str, domain: str = None) -> Optional[Dict[str, Any]]:
    """
    Optimized authentication that returns user data in a single database call
    """
    try:
        print(f"🔍 Attempting authentication for email: {email}, domain: {domain}")
        
        # Get Supabase client with domain configuration
        supabase = get_supabase(domain)
        print(f"✅ Supabase client created successfully for domain: {domain}")
        
        # Single database call to get user with password verification
        print(f"📊 Querying users table for email: {email}")
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        print(f"📋 Query response: {response}")
        print(f"📋 Response data: {response.data}")
        print(f"📋 Response count: {response.count}")
        
        if not response.data:
            print(f"❌ No user found with email: {email}")
            return None
        
        user = response.data[0]
        print(f"✅ User found: {user.get('email', 'N/A')} (ID: {user.get('id', 'N/A')})")
        
        # Check if user has password field
        if "password" not in user:
            print(f"❌ User record missing password field")
            return None
        
        # Verify password
        print(f"🔐 Verifying password...")
        if not verify_password(password, user["password"]):
            print(f"❌ Password verification failed for email: {email}")
            return None
        
        print(f"✅ Password verification successful")
        
        # Remove password from returned user data for security
        user.pop("password", None)
        print(f"✅ Authentication successful for email: {email}")
        return user
        
    except Exception as e:
        print(f"💥 Authentication error for email {email}: {str(e)}")
        print(f"💥 Error type: {type(e).__name__}")
        import traceback
        print(f"💥 Full traceback: {traceback.format_exc()}")
        return None

# Cache for user data to reduce database calls
_user_cache: Dict[str, Dict[str, Any]] = {}

async def get_user_by_email_cached(email: str, domain: str = None) -> Optional[Dict[str, Any]]:
    """
    Get user by email with caching to reduce database calls
    """
    # Create cache key that includes domain to avoid cross-domain cache issues
    cache_key = f"{domain}:{email}" if domain else email
    
    # Check cache first
    if cache_key in _user_cache:
        return _user_cache[cache_key]
    
    supabase = get_supabase(domain)
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        if not response.data:
            return None
        
        user = response.data[0]
        # Remove password from cached data
        user.pop("password", None)
        
        # Cache the user data
        _user_cache[cache_key] = user
        
        return user
        
    except Exception:
        return None

def clear_user_cache(email: str = None, domain: str = None):
    """
    Clear user cache - useful for logout or profile updates
    """
    if email:
        # Clear cache for specific email and domain combination
        if domain:
            cache_key = f"{domain}:{email}"
            _user_cache.pop(cache_key, None)
        else:
            # Clear all cache entries for this email across all domains
            keys_to_remove = [key for key in _user_cache.keys() if key.endswith(f":{email}") or key == email]
            for key in keys_to_remove:
                _user_cache.pop(key, None)
    else:
        _user_cache.clear()

# Optimized user registration with single database operation
async def register_user_optimized(email: str, password: str, first_name: str, last_name: str, domain: str = None) -> Optional[Dict[str, Any]]:
    """
    Optimized user registration that uses a single database operation with conflict handling
    """
    try:
        print(f"🔍 Starting user registration - Email: {email}, Domain: {domain}")
        
        # Get Supabase client with domain configuration
        supabase = get_supabase(domain)
        print(f"✅ Supabase client created successfully for domain: {domain}")
        
        # Hash the password
        hashed_password = get_password_hash(password)
        print(f"🔐 Password hashed successfully")
        
        # Prepare user data
        new_user = {
            "email": email,
            "password": hashed_password,
            "first_name": first_name,
            "last_name": last_name
        }
        
        print(f"📝 Inserting new user into database: {email}")
        
        # Insert with conflict detection
        response = supabase.table("users").insert(new_user).execute()
        
        print(f"📋 Insert response: {response}")
        print(f"📋 Response data: {response.data}")
        print(f"📋 Response count: {response.count}")
        
        if not response.data:
            print(f"❌ No data returned from insert operation")
            return None
        
        created_user = response.data[0]
        print(f"✅ User created successfully: {created_user.get('email', 'N/A')} (ID: {created_user.get('id', 'N/A')})")
        
        # Remove password from returned data for security
        created_user.pop("password", None)
        print(f"🔒 Password removed from response data")
        
        return created_user
        
    except Exception as e:
        print(f"💥 Registration error for {email}: {str(e)}")
        print(f"💥 Error type: {type(e).__name__}")
        
        # Check if it's a unique constraint violation (email already exists)
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["duplicate key", "unique constraint", "already exists", "duplicate entry"]):
            print(f"❌ User already exists: {email}")
            return None  # User already exists
        
        # Log the full error for debugging
        import traceback
        print(f"💥 Full traceback: {traceback.format_exc()}")
        raise e

async def check_user_exists(email: str, domain: str = None) -> bool:
    """
    Fast check if user exists without fetching full user data
    """
    supabase = get_supabase(domain)
    try:
        # Only select id to minimize data transfer
        response = supabase.table("users").select("id").eq("email", email).limit(1).execute()
        return len(response.data) > 0
    except Exception:
        return False
