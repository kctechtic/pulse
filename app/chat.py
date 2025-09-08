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
}

# Mapping of functions that use GET vs POST method
HTTP_METHODS = {
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
}


async def create_session_optimized(user_id: str, title: str = None) -> dict:
    """
    Optimized session creation with enhanced validation and error handling
    """
    try:
        if not user_id:
            raise ValueError("user_id is required")
        
        # Validate title length and content
        if title:
            title = title.strip()
            if len(title) > 200:
                title = title[:200] + "..."
            if not title:
                title = None
        
        supabase = get_supabase()
        
        # Create session with optimized insert
        session_data = {
            "user_id": user_id,
            "title": title or "New Chat"
        }
        
        resp = supabase.table("chat_sessions").insert(session_data).execute()
        
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


async def call_openai_streaming(user_message: str, tools, session_id: str, user_id: str):
    """
    Streaming OpenAI API call function for real-time responses
    """
    try:
        # Get chat history asynchronously
        history = get_history(session_id)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]

        # Check if this is the first message and generate title if needed
        if len(history) == 0:
            # This is the first message, generate a title asynchronously
            update_chat_title(session_id, user_message)

        # Get current date for context
        current_date = datetime.now()
        current_date_str = current_date.strftime("%Y-%m-%d")
        current_year = current_date.year

        system_message = {
                            "role": "system",
                            "content": (
                                            f"""You are a specialized eCommerce data analyst assistant for Shopify businesses.
                                                TODAY'S DATE IS {current_date_str} (Year: {current_year}).
                                                You are helping user {user_id} analyze Shopify orders, customers, discounts, and Klaviyo/Okendo reviews to uncover actionable insights.

                                                ### CRITICAL SCOPE RESTRICTION
                                                **YOU MUST ONLY RESPOND TO QUESTIONS RELATED TO ECOMMERCE ANALYTICS AND THE AVAILABLE SUPABASE FUNCTIONS.**
                                                - If a user asks about topics outside eCommerce analytics (like sports, celebrities, general knowledge, etc.), you MUST politely decline and redirect them to eCommerce topics.
                                                - ONLY use the available Supabase functions listed below.
                                                - If a question cannot be answered using the available functions, explain that it's outside your scope and suggest relevant eCommerce analytics questions instead.

                                                ### Core Role
                                                - You are NOT just answering — you are an **orchestrator** of multiple Supabase Edge Functions.
                                                - Analyze user queries → dynamically decide which function(s) to call → synthesize the results → deliver business insights.
                                                - You may call **multiple functions in sequence** to generate intelligent answers.
                                                - **ONLY respond to eCommerce analytics questions that can be answered using the available functions.**
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
                                                - getInactiveCustomers (days?) → Inactive customers
                                                - getCustomerOrders (email? | customer_id?) → Orders per customer
                                                - getCustomersStats (metric?, field?, from?, to?) → Customer statistics
                                                - getTopCustomersRepeatFrequency (top_n?, start_date?, end_date?, customer_emails?) → Top customers with repeat frequency
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
                                                - orchestrator (query) → Process natural language Shopify analytics query
                                                ---
                                                ### Multifunction Orchestration Rules
                                                1. **Function Routing**
                                                - Parse user query → determine best function(s).
                                                - Route dynamically. If multiple calls are needed, chain them.
                                                - Example: "Revenue trends last month" →
                                                    (a) getOrdersOverTime → (b) analyze trends.
                                                2. **Chaining & Reasoning**
                                                - Use results from one function to enrich or filter another.
                                                - Always produce a **final human-friendly insight**, not raw JSON.
                                                3. **Date Handling**
                                                - Relative dates ("last week", "past month") must resolve against TODAY ({current_date_str}, {current_year}).
                                                - Never use data from {current_year-1} unless explicitly requested.
                                                4. **Validation**
                                                - Ensure required parameters are present (e.g., order_id, rating ranges).
                                                - Enforce constraints (ratings 1–5, interval in [day, week, month], etc).
                                                5. **Error Handling**
                                                - If data missing → explain gracefully.
                                                - If multiple interpretations → state assumptions.
                                                6. **Out-of-Scope Handling**
                                                - If question is NOT about eCommerce analytics → politely decline and redirect.
                                                - Example: "I'm specialized in eCommerce analytics for Shopify businesses. I can help you analyze orders, customers, reviews, and marketing data. What would you like to know about your business performance?"
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

                                                **Example Out-of-Scope Response:**
                                                ---
                                                ❌ **Out of Scope Question**: "Who is Virat Kohli?"
                                                ✅ **Proper Response**: "I'm specialized in eCommerce analytics for Shopify businesses. I can help you analyze orders, customers, reviews, and marketing data. What would you like to know about your business performance? For example, I can show you revenue trends, top customers, or product reviews."
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

        # Call OpenAI with streaming
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=openai_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=4000,
            stream=True
        )

        # Handle streaming response
        async for chunk in handle_openai_streaming_response(stream, session_id, openai_messages):
            yield chunk

    except Exception as e:
        error_msg = f"Error in call_openai_streaming: {str(e)}"
        print(error_msg)
        save_message(session_id, "assistant", error_msg)
        yield {"type": "error", "content": error_msg}

async def handle_openai_streaming_response(stream, session_id: str, messages: list):
    """
    Handle streaming response from OpenAI API
    """
    try:
        accumulated_content = ""
        tool_calls = []
        current_tool_call = None
        
        for chunk in stream:
            if not chunk.choices:
                continue
                
            delta = chunk.choices[0].delta
            
            # Handle tool calls
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    if tool_call_delta.index is not None:
                        # Ensure we have enough tool calls in our list
                        while len(tool_calls) <= tool_call_delta.index:
                            tool_calls.append({
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            })
                        
                        current_tool_call = tool_calls[tool_call_delta.index]
                        
                        if tool_call_delta.id:
                            current_tool_call["id"] = tool_call_delta.id
                        if tool_call_delta.type:
                            current_tool_call["type"] = tool_call_delta.type
                        if tool_call_delta.function:
                            if tool_call_delta.function.name:
                                current_tool_call["function"]["name"] = tool_call_delta.function.name
                            if tool_call_delta.function.arguments:
                                current_tool_call["function"]["arguments"] += tool_call_delta.function.arguments
            
            # Handle regular content
            elif delta.content:
                accumulated_content += delta.content
                yield {
                    "type": "content",
                    "content": delta.content
                }
        
        # If we have tool calls, handle them
        if tool_calls and any(tc.get("function", {}).get("name") for tc in tool_calls):
            yield {"type": "tool_calls", "content": "Processing your request..."}
            
            # Add assistant's tool call request to messages
            messages.append({
                "role": "assistant",
                "content": accumulated_content,
                "tool_calls": tool_calls
            })
            
            # Execute each tool call
            for tool_call in tool_calls:
                try:
                    fn_name = tool_call["function"]["name"]
                    fn_args = json.loads(tool_call["function"]["arguments"] or "{}")
                    
                    yield {"type": "tool_execution", "content": f"Executing {fn_name}..."}
                    
                    # Call Supabase Edge Function directly with GPT's parameters
                    result = call_supabase_edge(fn_name, fn_args)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result, default=str)
                    })
                    
                except Exception as tool_error:
                    print(f"Error executing tool {fn_name}: {tool_error}")
                    error_result = {"error": f"Tool execution failed: {str(tool_error)}"}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(error_result)
                    })
            
            # Get final response from OpenAI with tool results
            yield {"type": "final_response", "content": "Generating final response..."}
            
            final_stream = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.1,
                max_tokens=4000,
                stream=True
            )
            
            final_content = ""
            for chunk in final_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    final_content += content
                    yield {
                        "type": "content",
                        "content": content
                    }
            
            # Save the final response
            if final_content:
                final_content = enhance_response_formatting(final_content)
                print(f"\n=== FINAL CHAT RESPONSE ===")
                print(final_content)
                print("=" * 50)
                save_message(session_id, "assistant", final_content)
        
        else:
            # No tool calls, just save the accumulated content
            if accumulated_content:
                accumulated_content = enhance_response_formatting(accumulated_content)
                print(f"\n=== FINAL CHAT RESPONSE (NO TOOL CALLS) ===")
                print(accumulated_content)
                print("=" * 50)
                save_message(session_id, "assistant", accumulated_content)
    
    except Exception as e:
        error_msg = f"Error handling streaming response: {str(e)}"
        print(f"\n=== CHAT ERROR ===")
        print(error_msg)
        print("=" * 50)
        save_message(session_id, "assistant", error_msg)
        yield {"type": "error", "content": error_msg}



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

async def get_chat_detail_optimized(session_id: str, user_id: str) -> dict:
    """
    Optimized function to get detailed chat information with single query approach
    """
    try:
        supabase = get_supabase()
        
        # Single optimized query to get session info and verify ownership
        session_query = f"""
        SELECT 
            cs.id,
            cs.title,
            cs.created_at,
            cs.user_id,
            COUNT(cm.id) as total_messages
        FROM chat_sessions cs
        LEFT JOIN chat_messages cm ON cs.id = cm.session_id
        WHERE cs.id = '{session_id}' AND cs.user_id = '{user_id}'
        GROUP BY cs.id, cs.title, cs.created_at, cs.user_id
        """
        
        try:
            # Try optimized SQL query first
            session_response = supabase.rpc('get_chat_detail_optimized', {
                'session_id_param': session_id,
                'user_id_param': user_id
            }).execute()
            
            if session_response.data:
                session_data = session_response.data[0]
            else:
                # Fallback to original approach if RPC doesn't exist
                session_data = await _get_chat_detail_fallback(supabase, session_id, user_id)
        except Exception:
            # Fallback to original approach if optimized query fails
            session_data = await _get_chat_detail_fallback(supabase, session_id, user_id)
        
        if not session_data:
            raise ValueError("Chat session not found or you don't have permission to view it")
        
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
            "title": session_data["title"],
            "created_at": session_data["created_at"],
            "user_id": user_id,
            "messages": messages or [],
            "total_messages": len(messages) if messages else 0
        }
        
    except Exception as e:
        print(f"Error getting optimized chat detail: {e}")
        raise

async def _get_chat_detail_fallback(supabase, session_id: str, user_id: str) -> dict:
    """
    Fallback method using original approach with ownership verification
    """
    # Verify the session belongs to the user
    session_check = (
        supabase.table("chat_sessions")
        .select("id, title, created_at, user_id")
        .eq("id", session_id)
        .eq("user_id", user_id)  # Add user_id filter to make query more efficient
        .execute()
        .data
    )
    
    if not session_check:
        return None
    
    session_info = session_check[0]
    
    # Get total message count
    total_count_response = (
        supabase.table("chat_messages")
        .select("id", count="exact")
        .eq("session_id", session_id)
        .execute()
    )
    total_messages = total_count_response.count or 0
    
    return {
        "id": session_info["id"],
        "title": session_info["title"],
        "created_at": session_info["created_at"],
        "user_id": session_info["user_id"],
        "total_messages": total_messages
    }


async def delete_chat_session_optimized(session_id: str, user_id: str) -> bool:
    """
    Optimized session deletion with enhanced validation and error handling
    """
    try:
        if not session_id or not session_id.strip():
            raise ValueError("Session ID is required")
        
        if not user_id or not user_id.strip():
            raise ValueError("User ID is required")
        
        session_id = session_id.strip()
        user_id = user_id.strip()
        
        supabase = get_supabase()
        
        # Single query to verify ownership and get session info
        session_check = (
            supabase.table("chat_sessions")
            .select("id, user_id, title")
            .eq("id", session_id)
            .eq("user_id", user_id)  # Add user_id filter to make query more efficient
            .execute()
            .data
        )
        
        if not session_check:
            raise ValueError("Chat session not found or you don't have permission to delete it")
        
        # Delete all messages in the session first (due to foreign key constraints)
        messages_deleted = supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        
        # Delete the session
        session_deleted = supabase.table("chat_sessions").delete().eq("id", session_id).execute()
        
        if not session_deleted.data:
            raise Exception("Failed to delete session")
        
        return True
        
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        raise

def enhance_response_formatting(response: str) -> str:
    """Clean up response by removing debug messages and improving formatting for better readability"""
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
    
    # Improve spacing and formatting for better readability
    import re
    
    # Add spacing around headers (## and ###)
    cleaned_response = re.sub(r'\n(#{2,3}[^\n]+)\n', r'\n\n\1\n\n', cleaned_response)
    
    # Add spacing around bullet points and lists
    cleaned_response = re.sub(r'\n(- [^\n]+)\n', r'\n\1\n', cleaned_response)
    
    # Add spacing before and after sections with emojis
    cleaned_response = re.sub(r'\n(- :[^:]+: [^\n]+)\n', r'\n\1\n\n', cleaned_response)
    
    # Add spacing around conclusion sections
    cleaned_response = re.sub(r'\n(### Conclusion)\n', r'\n\n\1\n\n', cleaned_response)
    cleaned_response = re.sub(r'\n(### Key Observations)\n', r'\n\n\1\n\n', cleaned_response)
    cleaned_response = re.sub(r'\n(### Sentiment Summary)\n', r'\n\n\1\n\n', cleaned_response)
    
    # Add spacing around call-to-action sections
    cleaned_response = re.sub(r'\n(:arrow_right: [^\n]+)\n', r'\n\n\1\n\n', cleaned_response)
    
    # Clean up excessive newlines (more than 2 consecutive)
    cleaned_response = re.sub(r'\n{3,}', '\n\n', cleaned_response)
    
    # Ensure proper spacing at the beginning and end
    cleaned_response = cleaned_response.strip()
    
    return cleaned_response
