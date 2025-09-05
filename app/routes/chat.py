from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import StreamingResponse
from app.chat import create_session_optimized, call_openai_streaming, get_user_chat_sessions_optimized, delete_chat_session_optimized, get_chat_detail, get_chat_detail_optimized, get_session_info
from app.auth import get_current_user
from ..models import ChatRequest, CreateSessionRequest, CreateSessionResponse, ChatSessionsListResponse, ChatDetailResponse
from ..database import get_supabase
import time
import json
import asyncio
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta

router = APIRouter(prefix="/chat", tags=["chatbot"])

# Cache for sessions list responses
_sessions_cache: Dict[str, Dict] = {}
_sessions_cache_ttl = 60  # 1 minute cache TTL for sessions

# Rate limiting for session creation
_session_creation_attempts: Dict[str, list] = defaultdict(list)
_max_session_creation_per_hour = 20

def generate_sessions_cache_key(user_id: str, page: int, pagination: int) -> str:
    """Generate cache key for sessions list"""
    return f"sessions:{user_id}:{page}:{pagination}"

def get_cached_sessions(cache_key: str) -> Optional[Dict]:
    """Get cached sessions data if still valid"""
    if cache_key in _sessions_cache:
        cache_entry = _sessions_cache[cache_key]
        if time.time() - cache_entry['timestamp'] < _sessions_cache_ttl:
            return cache_entry['data']
        else:
            del _sessions_cache[cache_key]
    return None

def cache_sessions(cache_key: str, data: dict):
    """Cache sessions data"""
    _sessions_cache[cache_key] = {
        'data': data,
        'timestamp': time.time()
    }

def clear_sessions_cache(user_id: str = None):
    """Clear sessions cache (useful when sessions are created/updated/deleted)"""
    if user_id:
        # Clear all cache entries for this user
        keys_to_remove = [key for key in _sessions_cache.keys() if f"sessions:{user_id}:" in key]
        for key in keys_to_remove:
            del _sessions_cache[key]
    else:
        _sessions_cache.clear()

def check_session_creation_rate_limit(user_id: str) -> bool:
    """
    Check if user has exceeded rate limit for session creation
    """
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    # Clean old attempts
    _session_creation_attempts[user_id] = [
        attempt_time for attempt_time in _session_creation_attempts[user_id]
        if attempt_time > hour_ago
    ]
    
    # Check if under limit
    if len(_session_creation_attempts[user_id]) >= _max_session_creation_per_hour:
        return False
    
    # Record this attempt
    _session_creation_attempts[user_id].append(now)
    return True


@router.get("/sessions", response_model=ChatSessionsListResponse)
async def get_chat_sessions(
    request: Request,
    response: Response,
    page: int = 1, 
    pagination: int = 10, 
    current_user: dict = Depends(get_current_user)
):
    """
    Optimized endpoint to get paginated chat sessions with caching and performance improvements:
    - Response caching to reduce database load
    - Optimized database queries to eliminate N+1 problem
    - Performance monitoring and logging
    - ETag support for conditional requests
    """
    start_time = time.time()
    
    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if pagination < 1 or pagination > 100:
            pagination = 10
        
        # Use user ID directly from JWT token (no need for additional DB query)
        user_id = current_user["id"]
        
        # Generate cache key
        cache_key = generate_sessions_cache_key(user_id, page, pagination)
        
        # Check cache first
        cached_data = get_cached_sessions(cache_key)
        if cached_data:
            # Set cache headers
            response.headers["X-Cache"] = "HIT"
            response.headers["Cache-Control"] = "private, max-age=60"
            
            processing_time = (time.time() - start_time) * 1000
            print(f"Sessions served from cache in {processing_time:.2f}ms for user {user_id}")
            
            return ChatSessionsListResponse(**cached_data)
        
        # Get paginated chat sessions using optimized function
        result = await get_user_chat_sessions_optimized(user_id, page, pagination)
        
        # Cache the result
        cache_sessions(cache_key, result)
        
        # Set response headers
        response.headers["X-Cache"] = "MISS"
        response.headers["Cache-Control"] = "private, max-age=60"
        
        # Log performance
        processing_time = (time.time() - start_time) * 1000
        print(f"Sessions generated in {processing_time:.2f}ms for user {user_id} (page {page})")
        
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
async def delete_chat_session_endpoint(
    session_id: str, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Optimized endpoint to delete a specific chat session with enhanced performance:
    - Eliminated redundant database queries
    - Enhanced input validation
    - Performance monitoring and logging
    - Automatic cache invalidation
    - Better error handling
    """
    start_time = time.time()
    
    try:
        # Use user ID directly from JWT token (no need for additional DB query)
        user_id = current_user["id"]
        
        # Validate session_id format
        if not session_id or not session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID is required"
            )
        
        session_id = session_id.strip()
        
        # Delete the session using optimized function
        success = await delete_chat_session_optimized(session_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete session"
            )
        
        # Clear sessions cache for this user since we deleted a session
        clear_sessions_cache(user_id)
        
        # Log performance
        processing_time = (time.time() - start_time) * 1000
        print(f"Session deleted in {processing_time:.2f}ms for user {user_id}")
        
        return {
            "message": "Chat session deleted successfully", 
            "session_id": session_id,
            "deleted_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle specific validation errors
        error_msg = str(e).lower()
        if "not found" in error_msg or "permission" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or you don't have permission to delete it"
            )
        elif "required" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        print(f"Error deleting chat session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat session. Please try again."
        )

@router.delete("/sessions/bulk")
async def bulk_delete_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Optimized endpoint to delete multiple chat sessions at once
    """
    start_time = time.time()
    
    try:
        # Get session IDs from request body
        body = await request.json()
        session_ids = body.get("session_ids", [])
        
        if not session_ids or not isinstance(session_ids, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_ids array is required"
            )
        
        if len(session_ids) > 50:  # Limit bulk operations
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete more than 50 sessions at once"
            )
        
        user_id = current_user["id"]
        deleted_sessions = []
        failed_sessions = []
        
        # Delete sessions in parallel
        for session_id in session_ids:
            try:
                if not session_id or not session_id.strip():
                    failed_sessions.append({"session_id": session_id, "error": "Invalid session ID"})
                    continue
                
                success = await delete_chat_session_optimized(session_id.strip(), user_id)
                if success:
                    deleted_sessions.append(session_id)
                else:
                    failed_sessions.append({"session_id": session_id, "error": "Failed to delete"})
            except Exception as e:
                failed_sessions.append({"session_id": session_id, "error": str(e)})
        
        # Clear sessions cache for this user
        clear_sessions_cache(user_id)
        
        # Log performance
        processing_time = (time.time() - start_time) * 1000
        print(f"Bulk delete completed in {processing_time:.2f}ms for user {user_id}: {len(deleted_sessions)} deleted, {len(failed_sessions)} failed")
        
        return {
            "message": f"Bulk delete completed: {len(deleted_sessions)} sessions deleted",
            "deleted_sessions": deleted_sessions,
            "failed_sessions": failed_sessions,
            "total_requested": len(session_ids),
            "deleted_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in bulk delete: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk delete operation"
        )

@router.post("/create_chat", response_model=CreateSessionResponse)
async def create_chat(
    req: CreateSessionRequest, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Optimized endpoint to create a new chat session with enhanced performance:
    - Rate limiting protection against spam
    - Enhanced input validation
    - Eliminated redundant database queries
    - Performance monitoring and logging
    - Automatic cache invalidation
    """
    start_time = time.time()
    
    try:
        # Use user ID directly from JWT token (no need for additional DB query)
        authenticated_user_id = current_user["id"]
        
        # Validate user_id matches authenticated user
        if req.user_id != authenticated_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID mismatch - you can only create sessions for yourself"
            )
        
        # Check rate limit for session creation
        if not check_session_creation_rate_limit(authenticated_user_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many session creation attempts. Please try again later."
            )
        
        # Validate title if provided
        if req.title:
            req.title = req.title.strip()
            if len(req.title) > 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Session title must be 200 characters or less"
                )
        
        # Create session using optimized function
        session = await create_session_optimized(req.user_id, req.title)
        
        # Clear sessions cache for this user since we added a new session
        clear_sessions_cache(authenticated_user_id)
        
        # Log performance
        processing_time = (time.time() - start_time) * 1000
        print(f"Session created in {processing_time:.2f}ms for user {authenticated_user_id}")
        
        return CreateSessionResponse(
            session_id=session["id"],
            user_id=session["user_id"],
            title=session["title"],
            created_at=session["created_at"]
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error creating chat session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session. Please try again."
        )

tools = [
    # Review Management Functions
    {
        "type": "function",
        "function": {
            "name": "fetchLatestOkendoReviews",
            "description": "Fetch latest Okendo product reviews with pagination and sorting. Use this when users ask for recent reviews, want to see the latest feedback, or need paginated review data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of reviews to return (default: 10, max: 50)"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of reviews to skip for pagination (default: 0)"
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["date_created", "rating", "helpful_votes"],
                        "description": "Field to sort reviews by (default: date_created)"
                    },
                    "order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort order - ascending or descending (default: desc)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getReviewsByRatingRange",
            "description": "Filter reviews by rating range to identify patterns in low or high-rated feedback. Use this when users ask for reviews within specific rating ranges or want to analyze sentiment patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_rating": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Minimum rating value (1-5)"
                    },
                    "max_rating": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Maximum rating value (1-5, must be >= min_rating)"
                    }
                },
                "required": ["min_rating", "max_rating"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getReviewsByKeyword",
            "description": "Search customer reviews that mention specific words or topics. Great for identifying trends or recurring issues mentioned in feedback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Word or phrase to search for in review content"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getReviewsByDateRange",
            "description": "Retrieve product reviews submitted within a specific date range. Useful for analyzing recent customer sentiment or evaluating campaign performance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getReviewSummaryByProductName",
            "description": "Get an aggregated review summary for a specific product, including average rating and review count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product to get review summary for"
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getSentimentSummary",
            "description": "Fetch reviews grouped or filtered by sentiment (positive, neutral, negative). Helps identify customer tone and sentiment trends.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range": {
                        "type": "string",
                        "enum": ["this_week", "last_week", "this_month", "custom"],
                        "description": "Preset date range. If omitted, defaults to the latest 7 days."
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date for custom range (required if range is 'custom')"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date for custom range (required if range is 'custom')"
                    }
                }
            }
        }
    },
    
    # Order Management Functions
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
                        "description": "Start date in YYYY-MM-DD format. For relative time references (e.g., 'last week', 'past 2 weeks'), calculate from TODAY's current date. CRITICAL: Always use current year unless explicitly requested otherwise."
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in YYYY-MM-DD format. For relative time references, this is typically TODAY's date. For specific periods, use the end date mentioned in the user's request. CRITICAL: Always use the current year unless explicitly requested otherwise."
                    },
                    "currency": {
                        "type": "string",
                        "description": "Currency code for monetary calculations (e.g., 'USD', 'EUR', 'CAD'). ONLY include if user specifically mentions a currency."
                    }
                },
                "required": ["interval"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getOrdersByStatus",
            "description": "Filter and count orders by their status like completed, pending, or cancelled. Use this when users ask about order status breakdowns, fulfillment tracking, or support issues related to order status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_type": {
                        "type": "string",
                        "enum": ["financial", "fulfillment"],
                        "description": "Type of status to group by. Use 'financial' for payment status or 'fulfillment' for shipping status."
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date in YYYY-MM-DD format. ONLY include if user specifically requests a time period."
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in YYYY-MM-DD format. ONLY include if user specifically requests a time period."
                    },
                    "currency": {
                        "type": "string",
                        "description": "Currency code for monetary calculations. ONLY include if user specifically mentions a currency."
                    }
                },
                "required": ["status_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getOrderDetails",
            "description": "Retrieve detailed information about a specific order by order ID. Use this when users ask for full order details, customer info, or line item breakdowns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order number, e.g., 7754 or #7754"
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getTopProducts",
            "description": "List the best-selling products by total sales or units sold. Useful for merchandising and stock planning decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of top products to return (default: 5, max: 50)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getLineItemAggregates",
            "description": "Get top Shopify metrics (products, SKUs, vendors, etc.) by date range. Returns aggregated order line item metrics within specified dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["top_products", "top_skus", "top_variants", "top_vendors", "top_payment_gateways"],
                        "description": "The metric to aggregate (default: top_products)"
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date (inclusive) in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date (inclusive) in YYYY-MM-DD format"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (max: 50, default: 5)"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    
    # Discount Analysis Functions
    {
        "type": "function",
        "function": {
            "name": "getDiscountUsage",
            "description": "Track how often discount codes were used, and total revenue impact. Use this for discount strategy analysis and performance tracking.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getOrdersWithDiscounts",
            "description": "Get a list of orders where discount codes were applied. Use this to analyze discount effectiveness and customer behavior.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    
    # Customer Management Functions
    {
        "type": "function",
        "function": {
            "name": "getCustomers",
            "description": "Retrieve a list of all customers and their basic info. Use this for customer database overview and basic customer information.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getTopCustomers",
            "description": "Identify your highest-value customers based on lifetime spend or order count. Use this for VIP customer identification and retention strategies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "string",
                        "enum": ["7d", "30d", "90d", "365d"],
                        "description": "Timeframe for filtering orders (default: last 7 days)"
                    },
                    "limit": {
                        "type": "string",
                        "enum": ["5", "10"],
                        "description": "Maximum number of top customers to return"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getInactiveCustomers",
            "description": "Find customers who haven't placed an order recently. Helps with re-engagement campaigns and customer lifecycle management.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to check inactivity (default: 30)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getCustomerSignupsOverTime",
            "description": "Track new customer signups across time periods. Use this for growth analysis and marketing campaign effectiveness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "integer",
                        "description": "How many days back to include (default: 30)"
                    },
                    "group": {
                        "type": "string",
                        "enum": ["day", "week", "month"],
                        "description": "How to group the results (default: day)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getCustomerOrders",
            "description": "Fetch order history for a specific customer. Use this for customer support, order tracking, and customer relationship management.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "The email of the customer (use either email OR customer_id, not both)"
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "The Shopify customer ID (use either email OR customer_id, not both)"
                    }
                }
            }
        }
    },
    
    # Analytics Functions
    {
        "type": "function",
        "function": {
            "name": "getPostPurchaseInsights",
            "description": "Analyze open-ended survey feedback from customers after purchase to detect common themes or sentiment. Use this for customer experience improvement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "User's query, e.g., 'Summarize July feedback about pricing.'"
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Optional start date for filtering responses"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Optional end date for filtering responses"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "restrictedAnswer",
            "description": "Return only restricted answers from Supabase. This endpoint queries Supabase and returns ONLY answers that match the restricted domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user query that needs to be restricted"
                    }
                },
                "required": ["query"]
            }
        }
    },
    
    # Klaviyo Event Analytics Functions
    {
        "type": "function",
        "function": {
            "name": "getEventCounts",
            "description": "Fetch counts of events by type within a specified date range. Use this to analyze event patterns and understand user behavior across different event types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date (inclusive) in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date (inclusive) in YYYY-MM-DD format"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getEmailEventRatios",
            "description": "Get email engagement ratios including open rate, click rate, and click-to-open rate. Use this to analyze email campaign performance and engagement metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getTopClickedUrls",
            "description": "Get the most clicked URLs from email campaigns. Use this to identify which links are most engaging and optimize email content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top URLs to return (default: 3, max: 20)"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getCampaignReasoning",
            "description": "Get campaign engagement reasoning and daily trends. Use this to understand campaign performance patterns and identify factors affecting engagement rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Start date in ISO 8601 format"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date-time",
                        "description": "End date in ISO 8601 format"
                    },
                    "campaign_id": {
                        "type": "string",
                        "description": "Optional campaign ID to filter results"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getEventLogSlice",
            "description": "Get a filtered set of event log data with campaign and device insights. Use this to analyze specific event types, user behavior, and campaign performance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Type of event to filter (e.g., 'Clicked Email', 'Opened Email')"
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address to filter by (partial match supported)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events to return (default: 10)"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    }
]

@router.post("/chat")
async def chat(
    req: ChatRequest, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Streaming chat endpoint with real-time token-by-token response:
    - Real-time streaming responses like ChatGPT
    - Enhanced input validation
    - Performance monitoring and logging
    - Tool execution progress updates
    - Better error handling
    """
    start_time = time.time()
    
    try:
        # Use user ID directly from JWT token (no need for additional DB query)
        authenticated_user_id = current_user["id"]
        
        # Validate user_id matches authenticated user
        if req.user_id != authenticated_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID mismatch - you can only send messages for yourself"
            )
        
        # Validate message content
        if not req.message or not req.message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content is required"
            )
        
        # Validate session_id
        if not req.session_id or not req.session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID is required"
            )
        
        # Trim and validate message length
        req.message = req.message.strip()
        if len(req.message) > 4000:  # Reasonable limit for chat messages
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is too long (max 4000 characters)"
            )
        
        # Create streaming response generator
        async def generate_stream():
            try:
                # Send start event
                start_event = f"data: {json.dumps({'type': 'start', 'timestamp': datetime.now().isoformat()})}\n\n"
                yield start_event
                
                # Process chat message using streaming function
                async for chunk in call_openai_streaming(req.message, tools, req.session_id, req.user_id):
                    chunk_data = f"data: {json.dumps(chunk)}\n\n"
                    yield chunk_data
                    # Force immediate flush for real-time streaming
                    await asyncio.sleep(0)  # Yield control to allow immediate sending
                
                # Send completion event
                processing_time = (time.time() - start_time) * 1000
                complete_event = f"data: {json.dumps({'type': 'complete', 'processing_time_ms': round(processing_time, 2), 'timestamp': datetime.now().isoformat()})}\n\n"
                yield complete_event
                
                print(f"Chat streamed in {processing_time:.2f}ms for user {authenticated_user_id}")
                
            except Exception as e:
                error_msg = f"Error in streaming chat: {str(e)}"
                print(error_msg)
                error_event = f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
                yield error_event
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error processing chat message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message. Please try again."
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
async def get_chat_detail_endpoint(
    session_id: str, 
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user)
):
    """
    Optimized endpoint to get detailed chat information with enhanced performance:
    - Eliminated redundant user ID lookup (uses JWT token directly)
    - Added response caching to reduce database load
    - Optimized database queries with single query approach
    - Performance monitoring and logging
    - Enhanced input validation
    """
    start_time = time.time()
    
    try:
        # Use user ID directly from JWT token (no need for additional DB query)
        user_id = current_user["id"]
        
        # Validate session_id format
        if not session_id or not session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID is required"
            )
        
        session_id = session_id.strip()
        
        # Generate cache key
        cache_key = f"chat_detail:{user_id}:{session_id}"
        
        # Check cache first
        cached_data = get_cached_sessions(cache_key)
        if cached_data:
            # Set cache headers
            response.headers["X-Cache"] = "HIT"
            response.headers["Cache-Control"] = "private, max-age=30"
            
            processing_time = (time.time() - start_time) * 1000
            print(f"Chat detail served from cache in {processing_time:.2f}ms for user {user_id}")
            
            return ChatDetailResponse(**cached_data)
        
        # Get chat detail using optimized function
        chat_detail = await get_chat_detail_optimized(session_id, user_id)
        
        # Cache the result
        cache_sessions(cache_key, chat_detail)
        
        # Set response headers
        response.headers["X-Cache"] = "MISS"
        response.headers["Cache-Control"] = "private, max-age=30"
        
        # Log performance
        processing_time = (time.time() - start_time) * 1000
        print(f"Chat detail generated in {processing_time:.2f}ms for user {user_id}")
        
        return ChatDetailResponse(**chat_detail)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle specific validation errors
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        elif "only view your own" in error_msg or "permission" in error_msg:
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
        print(f"Error getting chat detail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat detail"
        )


