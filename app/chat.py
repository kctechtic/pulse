import json
import requests
from openai import OpenAI
from datetime import datetime
from .database import get_supabase
from .config import settings

# Initialize OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Supabase configuration from environment
SUPABASE_BASE_URL = settings.supabase_edge_function_url
SUPABASE_API_KEY = settings.supabase_anon_key

# Mapping of tool names to Supabase Edge function endpoints
SUPABASE_FUNCTIONS = {
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
    "getTopCustomers": "get-top-customers",
    "getInactiveCustomers": "get-inactive-customers",
    "getCustomerSignupsOverTime": "get-customer-signups-over-time",
    "getCustomerOrders": "get-customer-orders",
    "getPostPurchaseInsights": "analyze-post-purchase-feedback",
    "restrictedAnswer": "scope-check",
    # Klaviyo Event Analytics Functions
    "getEventCounts": "get-event-counts",
    "getEmailEventRatios": "get-email-click-ratio",
    "getTopClickedUrls": "get-top-clicked-urls",
    "getCampaignReasoning": "campaign_reasoning",
    "getEventLogSlice": "get-event-log-slice"
}

# Mapping of functions that use GET vs POST method
HTTP_METHODS = {
    "getOrdersOverTime": "POST",
    "getOrdersByStatus": "POST",
    "fetchLatestOkendoReviews": "GET",
    "getReviewsByRatingRange": "GET",
    "getReviewsByKeyword": "GET",
    "getReviewsByDateRange": "GET",
    "getReviewSummaryByProductName": "GET",
    "getSentimentSummary": "POST",
    "getOrderDetails": "POST",
    "getTopProducts": "GET",
    "getLineItemAggregates": "POST",
    "getDiscountUsage": "POST",
    "getOrdersWithDiscounts": "GET",
    "getCustomers": "GET",
    "getTopCustomers": "GET",
    "getInactiveCustomers": "GET",
    "getCustomerSignupsOverTime": "GET",
    "getCustomerOrders": "GET",
    "getPostPurchaseInsights": "POST",
    "restrictedAnswer": "POST",
    # Klaviyo Event Analytics Functions
    "getEventCounts": "POST",
    "getEmailEventRatios": "POST",
    "getTopClickedUrls": "POST",
    "getCampaignReasoning": "POST",
    "getEventLogSlice": "POST"
}

def create_session(user_id: str, title: str = None):
    """Create a new chat session"""
    try:
        if not user_id:
            raise ValueError("user_id is required")
        
        supabase = get_supabase()
        resp = supabase.table("chat_sessions").insert({
            "user_id": user_id,
            "title": title or "New Chat"
        }).execute()
        
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        else:
            raise Exception("Failed to create session - no data returned")
    except Exception as e:
        print(f"Failed to create session: {str(e)}")
        raise

def get_session_info(session_id: str) -> dict:
    """Get basic session information by ID"""
    try:
        supabase = get_supabase()
        session = (
            supabase.table("chat_sessions")
            .select("id, title, created_at, user_id")
            .eq("id", session_id)
            .execute()
            .data
        )
        
        if session and len(session) > 0:
            return session[0]
        else:
            raise ValueError("Session not found")
            
    except Exception as e:  
        print(f"Error getting session info: {e}")
        raise

def update_chat_title(session_id: str, user_message: str):
    """Generate and update chat title based on first user message"""
    try:
        # Generate a title using OpenAI
        title_prompt = f"Generate a short, descriptive title (max 50 characters) for a chat conversation that starts with: '{user_message[:200]}...'"
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a title generator. Generate concise, descriptive titles for chat conversations. Keep titles under 50 characters and make them relevant to the conversation topic."
                },
                {
                    "role": "user",
                    "content": title_prompt
                }
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        generated_title = response.choices[0].message.content.strip()
        # Clean up the title and ensure it's not too long
        if generated_title:
            # Remove quotes if present
            generated_title = generated_title.strip('"\'')
            # Truncate if too long
            if len(generated_title) > 50:
                generated_title = generated_title[:47] + "..."
        else:
            generated_title = "New Chat"
        
        # Update the session title in the database
        supabase = get_supabase()
        supabase.table("chat_sessions").update({
            "title": generated_title
        }).eq("id", session_id).execute()
        
        return generated_title
        
    except Exception as e:
        print(f"Error generating chat title: {e}")
        # If title generation fails, use a fallback
        fallback_title = user_message[:30] + "..." if len(user_message) > 30 else user_message
        try:
            supabase = get_supabase()
            supabase.table("chat_sessions").update({
                "title": fallback_title
            }).eq("id", session_id).execute()
        except:
            pass
        return fallback_title

def call_openai(user_message: str, tools, session_id: str, user_id: str):
    """Main function to handle OpenAI API calls with tool support"""
    try:
        # Get chat history
        history = get_history(session_id)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]

        # Check if this is the first message and generate title if needed
        if len(history) == 0:
            # This is the first message, generate a title
            update_chat_title(session_id, user_message)

        # Get current date for context
        current_date = datetime.now()
        current_date_str = current_date.strftime("%Y-%m-%d")
        current_year = current_date.year

        # Add system message for eCommerce data analysis
        # system_message = {
        #     "role": "system",
        #     "content": (
        #         f"You are a specialized eCommerce data analyst assistant for Shopify businesses. TODAY'S DATE IS {current_date_str} (Year: {current_year}). "
        #         f"You are helping user {user_id} analyze Shopify orders and revenue data to uncover actionable insights. "
        #         f"Make your responses engaging and visually appealing by using appropriate emojis and clear formatting. "
        #         f"Always format data in the most appropriate way - use tables for structured data, lists for insights, and paragraphs for explanations. "
        #         f"AVAILABLE FUNCTIONS: "
        #         f"- getOrdersOverTime: for revenue trends, order patterns, and time-based analytics "
        #         f"- getOrdersByStatus: for order status breakdowns, fulfillment tracking, and support issues "
        #         f"- fetchLatestOkendoReviews: for fetching the latest Okendo reviews "
        #         f"- getReviewsByRatingRange: for filtering reviews by rating "
        #         f"- getReviewsByKeyword: for filtering reviews by keyword "
        #         f"- getReviewsByDateRange: for filtering reviews by date "
        #         f"- getReviewSummaryByProductName: for getting a summary of reviews for a specific product "
        #         f"- getSentimentSummary: for getting a sentiment summary of reviews "
        #         f"- getOrderDetails: for getting detailed information about a specific order "
        #         f"- getTopProducts: for getting the top-selling products "
        #         f"- getLineItemAggregates: for getting aggregated line item data "
        #         f"- getDiscountUsage: for analyzing discount usage across orders "
        #         f"- getOrdersWithDiscounts: for getting orders that used specific discounts "
        #         f"- getCustomers: for getting all customers "
        #         f"- getTopCustomers: for getting the top-spending customers "
        #         f"- getInactiveCustomers: for getting customers who haven't made orders in a while "
        #         f"- getCustomerSignupsOverTime: for tracking customer signup trends "
        #         f"- getCustomerOrders: for getting orders for a specific customer "
        #         f"- getPostPurchaseInsights: for analyzing post-purchase feedback "
        #         f"- restrictedAnswer: for providing answers that are restricted to certain scopes "
        #         f"KLAVIYO EVENT ANALYTICS FUNCTIONS: "
        #         f"- getEventCounts: for getting event counts by type within date ranges "
        #         f"- getEmailEventRatios: for email engagement ratios (open rate, click rate, etc.) "
        #         f"- getTopClickedUrls: for most clicked URLs from email campaigns "
        #         f"- getCampaignReasoning: for campaign engagement reasoning and daily trends "
        #         f"- getEventLogSlice: for filtered event log data with campaign and device insights "
        #         f"You are responsible for analyzing the user's request and determining which function to use and the appropriate parameters: "
        #         f"REVIEW FUNCTIONS: "
        #         f"- fetchLatestOkendoReviews (OPTIONAL: limit, offset, sort_by, order): Get latest Okendo reviews with pagination and sorting "
        #         f"- getReviewsByRatingRange (REQUIRED: min_rating, max_rating): Filter reviews by rating range (1-5) "
        #         f"- getReviewsByKeyword (REQUIRED: keyword): Search reviews containing specific words "
        #         f"- getReviewsByDateRange (REQUIRED: start_date, end_date): Get reviews within date range "
        #         f"- getReviewSummaryByProductName (REQUIRED: product_name): Get aggregated review stats for a product "
        #         f"- getSentimentSummary (OPTIONAL: range, start_date, end_date): Get sentiment analysis of reviews "
        #         f"ORDER FUNCTIONS: "
        #         f"- getOrdersOverTime (REQUIRED: interval, OPTIONAL: start_date, end_date): Revenue trends over time "
        #         f"- getOrdersByStatus (REQUIRED: status_type, OPTIONAL: start_date, end_date, currency): Order status breakdowns "
        #         f"- getOrderDetails (REQUIRED: order_id): Detailed order information by order number "
        #         f"- getTopProducts (OPTIONAL: limit): Top-selling products by revenue/quantity "
        #         f"- getLineItemAggregates (REQUIRED: start_date, end_date, OPTIONAL: metric, limit): Aggregated line item metrics "
        #         f"- getDiscountUsage (NO PARAMS): Discount code usage statistics "
        #         f"- getOrdersWithDiscounts (NO PARAMS): Orders that applied discounts "
        #         f"CUSTOMER FUNCTIONS: "
        #         f"- getCustomers (NO PARAMS): List all customers with basic info "
        #         f"- getTopCustomers (OPTIONAL: duration, limit): Top customers by total sales "
        #         f"- getInactiveCustomers (OPTIONAL: days): Customers inactive for specified days "
        #         f"- getCustomerSignupsOverTime (OPTIONAL: period, group): Customer signup trends "
        #         f"- getCustomerOrders (OPTIONAL: email, customer_id): Orders for specific customer "
        #         f"ANALYTICS FUNCTIONS: "
        #         f"- getPostPurchaseInsights (REQUIRED: question, OPTIONAL: start_date, end_date): Analyze post-purchase feedback "
        #         f"- restrictedAnswer (REQUIRED: query): Get restricted domain answers "
        #         f"KLAVIYO EVENT ANALYTICS FUNCTIONS: "
        #         f"- getEventCounts (REQUIRED: start_date, end_date): Get event counts by type within date range "
        #         f"- getEmailEventRatios (REQUIRED: start_date, end_date): Get email engagement ratios and rates "
        #         f"- getTopClickedUrls (REQUIRED: start_date, end_date, OPTIONAL: limit): Get top clicked URLs with counts "
        #         f"- getCampaignReasoning (REQUIRED: start_date, end_date, OPTIONAL: campaign_id): Get campaign engagement reasoning and trends "
        #         f"- getEventLogSlice (REQUIRED: start_date, end_date, OPTIONAL: event_type, email, limit): Get filtered event log data "
        #         f"PARAMETER RULES: "
        #         f"- For date parameters: ONLY include when user explicitly requests specific time periods "
        #         f"- For rating ranges: Use 1-5 scale, min_rating must be <= max_rating "
        #         f"- For intervals: Use 'day', 'week', or 'month' for time-based functions "
        #         f"- For status_type: Use 'financial' for payment status, 'fulfillment' for shipping status "
        #         f"- For metrics: Use 'top_products', 'top_skus', 'top_variants', 'top_vendors', 'top_payment_gateways' "
        #         f"- For Klaviyo functions: start_date and end_date must be in YYYY-MM-DD format "
        #         f"CRITICAL RULES: "
        #         f"- For functions with date parameters: ONLY include start_date/end_date when user explicitly requests specific time periods "
        #         f"- For rating-based functions: Ensure min_rating <= max_rating and both are between 1-5 "
        #         f"- For customer functions: Use email OR customer_id, not both "
        #         f"- For line item aggregates: metric must be one of the allowed values "
        #         f"- For sentiment analysis: range must be one of 'this_week', 'last_week', 'this_month', or 'custom' "
        #         f"- For Klaviyo functions: Always use YYYY-MM-DD format for dates "
        #         f"CRITICAL DATE RULE: You are working in {current_year}. When dealing with relative time references "
        #         f"(like 'last week', 'past 2 weeks', 'this month'), you MUST calculate dates relative to TODAY ({current_date_str}). "
        #         f"NEVER use dates from {current_year-1} or earlier unless explicitly requested. "
        #         f"For example: 'last two weeks' should be from 2 weeks ago to {current_date_str}, using {current_year}. "
        #         f"Current date context: The user wants recent, current data from {current_year}. "
        #         f"If you see 'last week', 'past week', 'recent', etc., always use dates from {current_year} and recent past. "
        #         f"Remember: 'last two weeks' means the most recent 2 weeks ending on {current_date_str}, not some arbitrary period from {current_year-1}. "
        #         f"RESPONSE FORMATTING: Format your responses exactly like ChatGPT with rich, professional formatting. "
        #         f"Use **bold** for important numbers and key findings. "
        #         f"Use relevant emojis to make responses engaging "
        #         f"FORMATTING RULES: "
        #         f"- Use markdown tables (| Column 1 | Column 2 |) for structured data like order lists, revenue breakdowns, product comparisons "
        #         f"- Use bullet points (-) for lists and insights "
        #         f"- Use numbered lists (1.) for step-by-step processes "
        #         f"- Use code blocks (```) for any code, SQL queries, or technical details "
        #         f"- Use headers (##, ###) to organize sections clearly "
        #         f"- Use blockquotes (>) for important callouts or warnings "
        #         f"- Use horizontal rules (---) to separate major sections "
        #         f"- Present data in the most readable format - tables for structured data, lists for insights, paragraphs for explanations "
        #         f"FORMATTING EXAMPLES: "
        #         f"- For order data: Use tables with columns like Order ID, Date, Amount, Status "
        #         f"- For revenue breakdowns: Use tables with Period, Revenue, Growth columns "
        #         f"- For product lists: Use tables with Product, Sales, Revenue columns "
        #         f"- For insights: Use bullet points with emojis "
        #         f"- For step-by-step analysis: Use numbered lists "
        #         f"- For warnings or important notes: Use blockquotes with ⚠️ emoji "
        #         f"Structure your response logically with clear sections and proper spacing. "
        #         f"RESPONSE ENDING: End responses naturally without generic phrases like 'feel free to ask' or 'let me know if you need help'. "
        #         f"Instead, end with specific, actionable next steps or relevant follow-up questions when appropriate. "
        #         f"GOOD ENDINGS: 'Would you like me to analyze the top-performing products?' or 'Should I investigate the revenue dip in Week 34?' "
        #         f"AVOID: Generic phrases like 'feel free to ask' or 'let me know if you need help'."
        #     )
        # }

        system_message = {
            "role": "system",
            "content": (
                f"""
                    You are a specialized eCommerce data analyst assistant for Shopify businesses.
                    TODAY'S DATE IS {current_date_str} (Year: {current_year}).
                    You are helping user {user_id} analyze Shopify orders, customers, discounts, and Klaviyo/Okendo reviews to uncover actionable insights.
                    ### Core Role
                    - You are NOT just answering — you are an **orchestrator** of multiple Supabase Edge Functions.
                    - Analyze user queries → dynamically decide which function(s) to call → synthesize the results → deliver business insights.
                    - You may call **multiple functions in sequence** to generate intelligent answers.
                    ---
                    ### AVAILABLE FUNCTIONS
                    #### Orders
                    - getOrdersOverTime (interval, start_date?, end_date?) → Revenue trends
                    - getOrdersByStatus (status_type, start_date?, end_date?, currency?) → Order breakdowns
                    - getOrderDetails (order_id) → Single order details
                    - getTopProducts (limit?) → Top-selling products
                    - getLineItemAggregates (start_date, end_date, metric?, limit?) → Product/variant/vendor aggregates
                    - getDiscountUsage () → Discount usage stats
                    - getOrdersWithDiscounts () → Orders that used discounts
                    #### Customers
                    - getCustomers () → List customers
                    - getTopCustomers (duration?, limit?) → Top spenders
                    - getInactiveCustomers (days?) → Inactive customers
                    - getCustomerSignupsOverTime (period?, group?) → Signup trends
                    - getCustomerOrders (email? | customer_id?) → Orders per customer
                    #### Reviews (Okendo)
                    - fetchLatestOkendoReviews (limit?, offset?, sort_by?, order?) → Latest reviews
                    - getReviewsByRatingRange (min_rating, max_rating) → Reviews filtered by rating
                    - getReviewsByKeyword (keyword) → Reviews with keyword
                    - getReviewsByDateRange (start_date, end_date) → Reviews by date range
                    - getReviewSummaryByProductName (product_name) → Aggregated review stats
                    - getSentimentSummary (range?, start_date?, end_date?) → Sentiment insights
                    #### Klaviyo Analytics
                    - getEventCounts (start_date, end_date) → Event counts by type
                    - getEmailEventRatios (start_date, end_date) → Open/click ratios
                    - getTopClickedUrls (start_date, end_date, limit?) → Top clicked URLs
                    - getCampaignReasoning (start_date, end_date, campaign_id?) → Campaign engagement reasoning
                    - getEventLogSlice (start_date, end_date, event_type?, email?, limit?) → Raw event log slice
                    #### Analytics
                    - getPostPurchaseInsights (question, start_date?, end_date?) → Post-purchase survey analysis
                    - restrictedAnswer (query) → Restricted answers
                    ---
                    ### Multifunction Orchestration Rules
                    1. **Function Routing**
                    - Parse user query → determine best function(s).
                    - Route dynamically. If multiple calls are needed, chain them.
                    - Example: “Top customers by revenue last month” →
                        (a) getOrdersOverTime → (b) aggregate by customer → (c) getTopCustomers.
                    2. **Chaining & Reasoning**
                    - Use results from one function to enrich or filter another.
                    - Always produce a **final human-friendly insight**, not raw JSON.
                    3. **Date Handling**
                    - Relative dates (“last week”, “past month”) must resolve against TODAY ({current_date_str}, {current_year}).
                    - Never use data from {current_year-1} unless explicitly requested.
                    4. **Validation**
                    - Ensure required parameters are present (e.g., order_id, rating ranges).
                    - Enforce constraints (ratings 1–5, interval in [day, week, month], etc).
                    5. **Error Handling**
                    - If data missing → explain gracefully.
                    - If multiple interpretations → state assumptions.
                    ---
                    ### Response Formatting
                    - Use tables for structured data (orders, products, revenue).
                    - Use bullet points for insights.
                    - Use headers (##, ###) for sections.
                    - Use emojis to make insights engaging.
                    - End with a relevant next-step suggestion, not a generic phrase.
                    **Example Output**
                    ---
                    ## :bar_chart: Revenue Trends (Last Month)
                    | Week | Revenue | Growth |
                    |------|---------|--------|
                    | W1   | $12,340 | —      |
                    | W2   | $14,210 | +15%   |
                    :fire: Growth peaked in Week 2, likely due to mid-month promotions.
                    ## :crown: Top Customers
                    | Name     | Spend |
                    |----------|-------|
                    | Sarah K. | $2,450|
                    | John D.  | $2,200|
                    :sparkles: Sarah & John contributed 15% of revenue.
                    :arrow_right: Should I break this down by discount usage?
                    ---
                    """
            )
        }

        # Prepare messages for OpenAI
        openai_messages = [system_message] + messages + [
            {
                "role": "user", 
                "content": f"Current date context: Today is {current_date_str} (Year {current_year}). Please use this as your reference for all relative time calculations."
            },
            {"role": "user", "content": user_message}
        ]
        
        # Save user message
        save_message(session_id, "user", user_message)

        # Call OpenAI with tools
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=openai_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=4000
        )

        return handle_openai_response(response, session_id, openai_messages)

    except Exception as e:
        error_msg = f"Error in call_openai: {str(e)}"
        print(error_msg)
        save_message(session_id, "assistant", error_msg)
        return error_msg

def handle_openai_response(response, session_id, messages):
    """Handle OpenAI response and tool calls"""
    try:
        message = response.choices[0].message

        # Handle tool calls
        if getattr(message, "tool_calls", None) and message.tool_calls:
            return handle_tool_calls(message.tool_calls, session_id, messages)
        else:
            # No tool call - provide a helpful response
            no_tool_message = "I understand your question, but I need to use the available data analysis tools to provide you with accurate information. Could you please rephrase your question to be more specific about what Shopify order or revenue data you'd like to analyze?"
            save_message(session_id, "assistant", no_tool_message)
            return no_tool_message

    except Exception as e:
        error_msg = f"Error handling OpenAI response: {str(e)}"
        print(error_msg)
        save_message(session_id, "assistant", error_msg)
        return error_msg

def handle_tool_calls(tool_calls, session_id, messages):
    """Handle multiple tool calls and return final response"""
    try:
        # Add assistant's tool call request to messages
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls
        })

        # Execute each tool call
        for tool_call in tool_calls:
            try:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments or "{}")
                
                print(f"\n🚀 EXECUTING TOOL: {fn_name}")
                print(f"📝 Tool Arguments: {json.dumps(fn_args, indent=2, default=str)}")
                print("-" * 60)
                
                # Call Supabase Edge Function directly with GPT's parameters
                result = call_supabase_edge(fn_name, fn_args)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)
                })

            except Exception as tool_error:
                print(f"Error executing tool {fn_name}: {tool_error}")
                error_result = {"error": f"Tool execution failed: {str(tool_error)}"}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(error_result)
                })

        # Get final response from OpenAI with tool results
        final_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            max_tokens=4000
        )

        final_answer = final_response.choices[0].message.content
        if not final_answer:
            final_answer = "I've processed your request using the available tools. Is there anything specific you'd like to know about the results?"
        
        # Ensure the response is well-formatted for UI display
        final_answer = enhance_response_formatting(final_answer)

        save_message(session_id, "assistant", final_answer)
        return final_answer

    except Exception as e:
        error_msg = f"Error handling tool calls: {str(e)}"
        print(error_msg)
        save_message(session_id, "assistant", error_msg)
        return error_msg

def call_supabase_edge(fn_name: str, args: dict) -> dict:
    """Call Supabase Edge Function with GPT's parameters directly"""
    try:
        mapped_name = SUPABASE_FUNCTIONS.get(fn_name, fn_name)
        url = f"{SUPABASE_BASE_URL}/{mapped_name}"
        
        # Print detailed API call information
        print("=" * 80)
        print("🔍 SUPABASE API CALL DEBUG INFO")
        print("=" * 80)
        print(f"📞 Function Name: {fn_name}")
        print(f"🔗 Mapped Endpoint: {mapped_name}")
        print(f"🌐 Full URL: {url}")
        print(f"📋 Parameters: {json.dumps(args, indent=2, default=str)}")
        print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)
        
        headers = {
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "apikey": SUPABASE_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Pacer-CIL-Chat/1.0"
        }
        
        # Determine HTTP method based on function
        http_method = HTTP_METHODS.get(fn_name, "POST")
        
        if http_method == "GET":
            # For GET requests, add parameters as query string
            if args:
                import urllib.parse
                query_params = urllib.parse.urlencode(args)
                url = f"{url}?{query_params}"
            print(f"📤 Making GET request to: {url}")
            response = requests.get(url, headers=headers, timeout=30)
        else:
            # For POST requests, send data in body
            print(f"📤 Making POST request to: {url}")
            print(f"📦 Request payload: {json.dumps(args, indent=2, default=str)}")
            response = requests.post(url, headers=headers, json=args, timeout=30)
        
        print(f"📥 Response Status: {response.status_code}")
        print(f"📄 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"✅ Success Response: {json.dumps(result, indent=2, default=str)}")
                print("=" * 80)
                return result
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON Decode Error: {e}")
                print(f"📄 Raw Response: {response.text}")
                print("=" * 80)
                return {"data": response.text, "warning": "Response was not valid JSON"}
        else:
            error_msg = f"Supabase function returned status {response.status_code}: {response.text}"
            print(f"❌ Error Response: {error_msg}")
            print("=" * 80)
            return {"error": error_msg, "status_code": response.status_code}
            
    except requests.exceptions.Timeout:
        error_msg = "Request to Supabase function timed out"
        print(f"⏰ Timeout Error: {error_msg}")
        print("=" * 80)
        return {"error": error_msg}
    except requests.exceptions.RequestException as req_err:
        error_msg = f"Request to Supabase function failed: {str(req_err)}"
        print(f"🌐 Request Error: {error_msg}")
        print("=" * 80)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error calling Supabase function: {str(e)}"
        print(f"💥 Unexpected Error: {error_msg}")
        print("=" * 80)
        return {"error": error_msg}

def save_message(session_id: str, role: str, content: str):
    """Save message to database"""
    try:
        if not content or content.strip() == "":
            content = "Empty message"
        
        supabase = get_supabase()
        supabase.table("chat_messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        print(f"Error saving message: {e}")

def get_history(session_id: str) -> list:
    """Get chat history for a session"""
    try:
        supabase = get_supabase()
        history = (
            supabase.table("chat_messages")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
            .data
        )
        return history or []
    except Exception as e:
        print(f"Error getting history: {e}")
        return []

async def get_user_chat_sessions_optimized(user_id: str, page: int = 1, pagination: int = 10) -> dict:
    """
    Optimized function to get paginated chat sessions with single query approach
    """
    try:
        supabase = get_supabase()
        
        # Calculate offset for pagination
        offset = (page - 1) * pagination
        
        # Single optimized query to get sessions with message counts and last messages
        # Using a more efficient approach with window functions if supported
        sessions_query = f"""
        WITH session_stats AS (
            SELECT 
                cs.id,
                cs.title,
                cs.created_at,
                COUNT(cm.id) as message_count,
                MAX(cm.created_at) as last_message_time,
                FIRST_VALUE(cm.content) OVER (
                    PARTITION BY cs.id 
                    ORDER BY cm.created_at DESC 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) as last_message_content
            FROM chat_sessions cs
            LEFT JOIN chat_messages cm ON cs.id = cm.session_id
            WHERE cs.user_id = '{user_id}'
            GROUP BY cs.id, cs.title, cs.created_at
        )
        SELECT 
            id,
            title,
            created_at,
            message_count,
            last_message_time,
            CASE 
                WHEN last_message_content IS NOT NULL THEN 
                    CASE 
                        WHEN LENGTH(last_message_content) > 100 THEN 
                            LEFT(last_message_content, 100) || '...'
                        ELSE last_message_content
                    END
                ELSE 'No messages yet'
            END as last_message
        FROM session_stats
        ORDER BY created_at DESC
        LIMIT {pagination} OFFSET {offset}
        """
        
        # Get total count in parallel
        total_count_response = (
            supabase.table("chat_sessions")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        total_sessions = total_count_response.count or 0
        
        # Execute the optimized query
        try:
            # Try the optimized SQL query first
            sessions_response = supabase.rpc('get_user_sessions_optimized', {
                'user_id_param': user_id,
                'limit_param': pagination,
                'offset_param': offset
            }).execute()
            
            if sessions_response.data:
                sessions = sessions_response.data
            else:
                # Fallback to the original approach if RPC doesn't exist
                sessions = await _get_sessions_fallback(supabase, user_id, pagination, offset)
        except Exception:
            # Fallback to original approach if optimized query fails
            sessions = await _get_sessions_fallback(supabase, user_id, pagination, offset)
        
        # Calculate pagination metadata
        total_pages = (total_sessions + pagination - 1) // pagination if total_sessions > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1
        
        return {
            "sessions": sessions or [],
            "total_sessions": total_sessions,
            "page": page,
            "pagination": pagination,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev
        }
        
    except Exception as e:
        print(f"Error getting user chat sessions: {e}")
        return {
            "sessions": [],
            "total_sessions": 0,
            "page": page,
            "pagination": pagination,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False
        }

async def _get_sessions_fallback(supabase, user_id: str, pagination: int, offset: int) -> list:
    """
    Fallback method using optimized batch queries instead of N+1
    """
    # Get paginated chat sessions
    sessions = (
        supabase.table("chat_sessions")
        .select("id, title, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + pagination - 1)
        .execute()
        .data
    )
    
    if not sessions:
        return []
    
    session_ids = [session["id"] for session in sessions]
    
    # Batch query for message counts
    message_counts = {}
    if session_ids:
        counts_response = (
            supabase.table("chat_messages")
            .select("session_id", count="exact")
            .in_("session_id", session_ids)
            .execute()
        )
        
        # Group counts by session_id
        for count_data in counts_response.data:
            message_counts[count_data["session_id"]] = count_data.get("count", 0)
    
    # Batch query for last messages
    last_messages = {}
    if session_ids:
        # Get the most recent message for each session
        for session_id in session_ids:
            last_msg = (
                supabase.table("chat_messages")
                .select("content, created_at")
                .eq("session_id", session_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            
            if last_msg:
                last_messages[session_id] = {
                    "content": last_msg[0]["content"],
                    "created_at": last_msg[0]["created_at"]
                }
    
    # Combine all data
    for session in sessions:
        session_id = session["id"]
        session["message_count"] = message_counts.get(session_id, 0)
        
        if session_id in last_messages:
            msg_content = last_messages[session_id]["content"]
            session["last_message"] = msg_content[:100] + "..." if len(msg_content) > 100 else msg_content
            session["last_message_time"] = last_messages[session_id]["created_at"]
        else:
            session["last_message"] = "No messages yet"
            session["last_message_time"] = None
    
    return sessions

def get_user_chat_sessions(user_id: str, page: int = 1, pagination: int = 10) -> dict:
    """
    Legacy function for backward compatibility - calls the optimized version
    """
    import asyncio
    return asyncio.run(get_user_chat_sessions_optimized(user_id, page, pagination))

def get_chat_detail(session_id: str, user_id: str) -> dict:
    """Get detailed chat information including all messages for a specific session"""
    try:
        supabase = get_supabase()
        
        # First verify the session belongs to the user
        session_check = (
            supabase.table("chat_sessions")
            .select("id, title, created_at, user_id")
            .eq("id", session_id)
            .execute()
            .data
        )
        
        if not session_check:
            raise ValueError("Chat session not found")
        
        if session_check[0]["user_id"] != user_id:
            raise ValueError("You can only view your own chat sessions")
        
        session_info = session_check[0]
        
        # Get all messages for this session
        messages = (
            supabase.table("chat_messages")
            .select("id, role, content, created_at, session_id")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
            .data
        )
        
        return {
            "session_id": session_id,
            "title": session_info["title"],
            "created_at": session_info["created_at"],
            "user_id": user_id,
            "messages": messages or [],
            "total_messages": len(messages) if messages else 0
        }
        
    except Exception as e:
        print(f"Error getting chat detail: {e}")
        raise

def delete_chat_session(session_id: str, user_id: str) -> bool:
    """Delete a chat session and all its messages - requires user ownership verification"""
    try:
        supabase = get_supabase()
        
        # First verify the session belongs to the user
        session_check = (
            supabase.table("chat_sessions")
            .select("id, user_id")
            .eq("id", session_id)
            .execute()
            .data
        )
        
        if not session_check:
            raise ValueError("Chat session not found")
        
        if session_check[0]["user_id"] != user_id:
            raise ValueError("You can only delete your own chat sessions")
        
        # Delete all messages in the session first (due to foreign key constraints)
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        
        # Delete the session
        supabase.table("chat_sessions").delete().eq("id", session_id).execute()
        
        return True
        
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        raise

def enhance_response_formatting(response: str) -> str:
    """Clean up response by removing debug messages while preserving GPT's natural formatting"""
    if not response:
        return response
    
    # Clean up debug messages and unnecessary text
    lines = response.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove debug messages and connection info
        if line.strip().startswith('> [debug]') or line.strip().startswith('[debug]'):
            continue
        if 'Talked to' in line and 'supabase.co' in line:
            continue
        if line.strip() == '':
            cleaned_lines.append(line)
            continue
        
        cleaned_lines.append(line)
    
    # Rejoin and clean up extra whitespace
    cleaned_response = '\n'.join(cleaned_lines).strip()
    
    # Ensure proper spacing around sections
    cleaned_response = cleaned_response.replace('\n\n\n', '\n\n')
    
    return cleaned_response
