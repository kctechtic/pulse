# Edge Functions Integration - Pacer CIL Chat System

## Overview
This document outlines the complete integration of Supabase Edge Functions into the Pacer CIL chat system, enabling comprehensive e-commerce data analysis capabilities.

## Integrated Functions

### 1. Review Management Functions

#### `fetchLatestOkendoReviews` → `/okendo-review-query`
- **Method**: GET
- **Purpose**: Fetch latest Okendo product reviews with pagination and sorting
- **Parameters**: 
  - `limit` (optional): Number of reviews to return (default: 10)
  - `offset` (optional): Number of reviews to skip (default: 0)
  - `sort_by` (optional): Field to sort by (default: "date_created")
  - `order` (optional): Sort order "asc" or "desc" (default: "desc")

#### `getReviewsByRatingRange` → `/get-reviews-by-rating-range`
- **Method**: GET
- **Purpose**: Filter reviews by rating range
- **Parameters**:
  - `min_rating` (required): Minimum rating (1-5)
  - `max_rating` (required): Maximum rating (1-5)

#### `getReviewsByKeyword` → `/get-reviews-by-keyword`
- **Method**: GET
- **Purpose**: Search reviews containing specific keywords
- **Parameters**:
  - `keyword` (required): Word or phrase to search for

#### `getReviewsByDateRange` → `/get-reviews-by-date-range`
- **Method**: GET
- **Purpose**: Get reviews within a specific date range
- **Parameters**:
  - `start_date` (required): Start date (YYYY-MM-DD)
  - `end_date` (required): End date (YYYY-MM-DD)

#### `getReviewSummaryByProductName` → `/get-review-summary-by-product-name`
- **Method**: GET
- **Purpose**: Get aggregated review statistics for a specific product
- **Parameters**:
  - `product_name` (required): Name of the product to analyze

#### `getSentimentSummary` → `/get-reviews-by-sentiment`
- **Method**: POST
- **Purpose**: Get sentiment analysis of reviews
- **Parameters**:
  - `range` (optional): Preset range ("this_week", "last_week", "this_month", "custom")
  - `start_date` (required if range="custom"): Start date
  - `end_date` (required if range="custom"): End date

### 2. Order Management Functions

#### `getOrdersOverTime` → `/get-orders-over-time`
- **Method**: POST
- **Purpose**: Analyze revenue trends over time
- **Parameters**:
  - `interval` (required): Time grouping ("day", "week", "month")
  - `start_date` (optional): Start date for analysis
  - `end_date` (optional): End date for analysis
  - `currency` (optional): Currency filter

#### `getOrdersByStatus` → `/get-orders-by-status`
- **Method**: POST
- **Purpose**: Group orders by financial or fulfillment status
- **Parameters**:
  - `status_type` (required): "financial" or "fulfillment"
  - `start_date` (optional): Start date filter
  - `end_date` (optional): End date filter
  - `currency` (optional): Currency filter

#### `getOrderDetails` → `/get-order-details`
- **Method**: POST
- **Purpose**: Get detailed information about a specific order
- **Parameters**:
  - `order_id` (required): Order number or ID

#### `getTopProducts` → `/get-top-products`
- **Method**: GET
- **Purpose**: Get top-selling products by revenue/quantity
- **Parameters**:
  - `limit` (optional): Number of products to return (default: 5)

#### `getLineItemAggregates` → `/get-line-item-aggregates`
- **Method**: POST
- **Purpose**: Get aggregated line item metrics
- **Parameters**:
  - `start_date` (required): Start date for analysis
  - `end_date` (required): End date for analysis
  - `metric` (optional): Type of aggregation ("top_products", "top_skus", "top_variants", "top_vendors", "top_payment_gateways")
  - `limit` (optional): Number of results (default: 5)

### 3. Discount Analysis Functions

#### `getDiscountUsage` → `/get-discount-usage`
- **Method**: POST
- **Purpose**: Analyze discount code usage statistics
- **Parameters**: None (uses default settings)

#### `getOrdersWithDiscounts` → `/get-orders-with-discounts`
- **Method**: GET
- **Purpose**: Get orders that applied discount codes
- **Parameters**: None

### 4. Customer Management Functions

#### `getCustomers` → `/get-customers`
- **Method**: GET
- **Purpose**: Get list of all customers with basic information
- **Parameters**: None

#### `getTopCustomers` → `/get-top-customers`
- **Method**: GET
- **Purpose**: Get top customers by total sales
- **Parameters**:
  - `duration` (optional): Timeframe ("7d", "30d", "90d", "365d")
  - `limit` (optional): Number of customers to return ("5" or "10")

#### `getInactiveCustomers` → `/get-inactive-customers`
- **Method**: GET
- **Purpose**: Find customers who haven't placed orders recently
- **Parameters**:
  - `days` (optional): Number of days to check inactivity (default: 30)

#### `getCustomerSignupsOverTime` → `/get-customer-signups-over-time`
- **Method**: GET
- **Purpose**: Track customer signup trends over time
- **Parameters**:
  - `period` (optional): Days back to include (default: 30)
  - `group` (optional): Grouping interval ("day", "week", "month")

#### `getCustomerOrders` → `/get-customer-orders`
- **Method**: GET
- **Purpose**: Get order history for a specific customer
- **Parameters**:
  - `email` (optional): Customer email address
  - `customer_id` (optional): Shopify customer ID

### 5. Analytics Functions

#### `getPostPurchaseInsights` → `/analyze-post-purchase-feedback`
- **Method**: POST
- **Purpose**: Analyze post-purchase survey feedback
- **Parameters**:
  - `question` (required): User's query for analysis
  - `start_date` (optional): Start date for filtering
  - `end_date` (optional): End date for filtering

#### `restrictedAnswer` → `/scope-check`
- **Method**: POST
- **Purpose**: Get restricted domain answers from Supabase
- **Parameters**:
  - `query` (required): The user query that needs to be restricted

## Implementation Details

### HTTP Method Handling
The system automatically determines whether to use GET or POST based on the function:
- **GET functions**: Parameters are added as query string
- **POST functions**: Parameters are sent in request body

### Parameter Validation
The system includes comprehensive parameter validation rules:
- Date parameters are only included when explicitly requested
- Rating ranges must be valid (1-5, min ≤ max)
- Required parameters are enforced
- Optional parameters are only included when relevant

### Error Handling
- Comprehensive error logging and debugging
- Graceful fallbacks for failed API calls
- User-friendly error messages

### Response Formatting
- Natural language responses using GPT-4
- Structured data presentation
- Bold formatting for important metrics
- Logical organization of information

## Usage Examples

### Review Analysis
- "Find reviews for the Protein Shake with rating 3 and below"
- "Get negative feedback on skincare products from last month"
- "Show me reviews that mention delivery issues"

### Order Analysis
- "How many orders do we have by status?"
- "Show me revenue trends over the last 30 days"
- "Get details for order #12345"

### Customer Insights
- "Who are our top 10 customers?"
- "Find customers who haven't ordered in 90 days"
- "Show customer signup trends this month"

### Product Performance
- "Which products sold the most this month?"
- "Get top SKUs by revenue for Q1"
- "Show me top vendors by order volume"

## Configuration

The system uses environment variables for configuration:
- `SUPABASE_EDGE_FUNCTION_URL`: Base URL for edge functions
- `SUPABASE_ANON_KEY`: API key for authentication

All functions are automatically mapped and available for use in the chat interface.
