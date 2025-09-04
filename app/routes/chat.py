from fastapi import APIRouter, Depends, HTTPException, status
from app.chat import create_session, call_openai, get_user_chat_sessions, delete_chat_session, get_chat_detail, get_session_info
from app.auth import get_current_user
from ..models import ChatRequest, CreateSessionRequest, CreateSessionResponse, ChatSessionsListResponse, ChatDetailResponse
from ..database import get_supabase

router = APIRouter(prefix="/chat", tags=["chatbot"])



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


