from pydantic_settings import BaseSettings
from typing import Optional, Dict
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase projects configuration
supabase_projects = {
    "pulse.pacer.studio": {
        "project_url": "https://roovzqstfwpvvybejjss.supabase.co/",
        "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvb3Z6cXN0ZndwdnZ5YmVqanNzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI1ODAxMjIsImV4cCI6MjA2ODE1NjEyMn0.AbcXk30FDednbYS7z8euxY5tWH4gAqicO03yoNPvBRs"
    },
    "thebodyshop.pacer.studio": {
        "project_url": "https://tfewbenccurmrtahazgr.supabase.co/",
        "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRmZXdiZW5jY3VybXJ0YWhhemdyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDA4NzI2NywiZXhwIjoyMDc1NjYzMjY3fQ.HXXIdPSlTJgJtCraCC8MmGdb0YBir8XVrgtHTcrClZ8"
    }
}

# Host-specific Supabase Functions mapping
SUPABASE_FUNCTIONS = {
    "pulse.pacer.studio": {
        "getOrdersOverTime": "get-orders-over-time",
        "getOrdersByStatus": "get-orders-by-status",
        "fetchLatestOkendoReviews": "okendo-review-query",
        "getReviewsByRatingRange": "get-reviews-by-rating-range",
        "getReviewsByKeyword": "get-reviews-by-keyword",
        "getReviewsByDateRange": "get-reviews-by-date-range",
        "getReviewSummaryByProductName": "get-review-summary-by-product-name",
        "getSentimentSummary": "get-reviews-by-sentiment",
        "getOrderDetails": "get-order-details",
        "getTopProducts": "get-top-products",
        "getLineItemAggregates": "get-line-item-aggregates",
        "getDiscountUsage": "get-discount-usage",
        "getOrdersWithDiscounts": "get-orders-with-discounts",
        "getCustomers": "get-customers",
        "getInactiveCustomers": "get-inactive-customers",
        "getCustomerOrders": "get-customer-orders",
        "getPostPurchaseInsights": "analyze-post-purchase-feedback",
        "getCustomersStats": "get-customers-stats",
        "getTopCustomersRepeatFrequency": "get-top-customers-repeat-frequency",
        "orchestrator": "orchestrator",
        # Klaviyo Event Analytics Functions
        "getEventCounts": "get-event-counts",
        "getEmailEventRatios": "get-email-click-ratio",
        "getTopClickedUrls": "get-top-clicked-urls",
        "getCampaignReasoning": "campaign_reasoning",
        "getEventLogSlice": "get-event-log-slice"
    },
    "thebodyshop.pacer.studio": {
        "getShopifyMetrics": "agreegation-thebodyshop"
    }
}

# Host-specific HTTP Methods mapping
HTTP_METHODS = {
    "pulse.pacer.studio": {
        "getOrdersOverTime": "POST",
        "getOrdersByStatus": "POST",
        "fetchLatestOkendoReviews": "GET",
        "getReviewsByRatingRange": "GET",
        "getReviewsByKeyword": "GET",
        "getReviewsByDateRange": "POST",
        "getReviewSummaryByProductName": "GET",
        "getSentimentSummary": "POST",
        "getOrderDetails": "POST",
        "getTopProducts": "GET",
        "getLineItemAggregates": "POST",
        "getDiscountUsage": "POST",
        "getOrdersWithDiscounts": "GET",
        "getCustomers": "GET",
        "getInactiveCustomers": "GET",
        "getCustomerOrders": "GET",
        "getPostPurchaseInsights": "POST",
        "getCustomersStats": "POST",
        "getTopCustomersRepeatFrequency": "POST",
        "orchestrator": "POST",
        # Klaviyo Event Analytics Functions
        "getEventCounts": "POST",
        "getEmailEventRatios": "POST",
        "getTopClickedUrls": "POST",
        "getCampaignReasoning": "POST",
        "getEventLogSlice": "POST"
    },
    "thebodyshop.pacer.studio": {
        "getShopifyMetrics": "POST"
    }
}

def get_supabase_functions(domain: str = None) -> Dict[str, str]:
    """
    Get Supabase functions mapping based on domain.
    Returns the appropriate function mapping for the given domain.
    """
    if not domain:
        return SUPABASE_FUNCTIONS.get("pulse.pacer.studio", {})
    
    clean_domain = domain.split(':')[0]
    return SUPABASE_FUNCTIONS.get(clean_domain, SUPABASE_FUNCTIONS.get("pulse.pacer.studio", {}))

def get_http_methods(domain: str = None) -> Dict[str, str]:
    """
    Get HTTP methods mapping based on domain.
    Returns the appropriate HTTP methods mapping for the given domain.
    """
    if not domain:
        return HTTP_METHODS.get("pulse.pacer.studio", {})
    
    clean_domain = domain.split(':')[0]
    return HTTP_METHODS.get(clean_domain, HTTP_METHODS.get("pulse.pacer.studio", {}))

def get_supabase_config(domain: str = None) -> Dict[str, str]:
    """
    Get Supabase configuration based on domain.
    If domain is not provided or not found, returns default configuration.
    """
    try:
        print(f"🔧 Getting Supabase config for domain: {domain}")
        
        if not domain:
            # Return default configuration from environment variables
            config = {
                "project_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
                "api_key": os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
            }
            print(f"📋 Using default config: {config['project_url']}")
            return config
        
        # Extract domain from host header (remove port if present)
        clean_domain = domain.split(':')[0]
        print(f"🧹 Cleaned domain: {clean_domain}")
        
        # Return configuration for the domain or default if not found
        if clean_domain in supabase_projects:
            config = supabase_projects[clean_domain]
            print(f"✅ Found domain-specific config for {clean_domain}: {config['project_url']}")
            return config
        else:
            config = {
                "project_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
                "api_key": os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
            }
            print(f"⚠️  Domain {clean_domain} not found, using default config: {config['project_url']}")
            return config
            
    except Exception as e:
        print(f"💥 Error getting Supabase config: {str(e)}")
        # Fallback to default configuration
        return {
            "project_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
            "api_key": os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
        }

class Settings(BaseSettings):
    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "http://localhost:54321")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
    
    # JWT Configuration
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "your_secret_key")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = os.getenv("JWT_EXPIRE_MINUTES", 30)
    
    # Database Configuration
    database_url: Optional[str] = os.getenv("DATABASE_URL", "http://localhost:54321")
    
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "your_openai_api_key")
    
    # Supabase Edge Function Configuration
    supabase_edge_function_url: str = os.getenv("SUPABASE_EDGE_FUNCTION_URL", "https://your-project.supabase.co/functions/v1")
    supabase_edge_function_key: str = os.getenv("SUPABASE_EDGE_FUNCTION_KEY", "your_supabase_edge_function_key")
    
    class Config:
        env_file = ".env"

settings = Settings()
