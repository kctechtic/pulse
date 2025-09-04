# Klaviyo Edge Functions Integration

This document describes the integration of Klaviyo Event Analytics edge functions into the Pacer CIL FastAPI project.

## Overview

The following Klaviyo edge functions have been integrated into the project:

1. **getEventCounts** - Fetch counts of events by type within date ranges
2. **getEmailEventRatios** - Get email engagement ratios (open rate, click rate, etc.)
3. **getTopClickedUrls** - Get most clicked URLs from email campaigns
4. **getCampaignReasoning** - Get campaign engagement reasoning and daily trends
5. **getEventLogSlice** - Get filtered event log data with campaign and device insights

## Integration Details

### 1. Edge Function Mappings

The functions are mapped in `app/chat.py`:

```python
SUPABASE_FUNCTIONS = {
    # ... existing functions ...
    # Klaviyo Event Analytics Functions
    "getEventCounts": "get-event-counts",
    "getEmailEventRatios": "get-email-click-ratio",
    "getTopClickedUrls": "get-top-clicked-urls",
    "getCampaignReasoning": "campaign_reasoning",
    "getEventLogSlice": "get-event-log-slice"
}
```

### 2. HTTP Methods

All Klaviyo functions use POST method:

```python
HTTP_METHODS = {
    # ... existing functions ...
    # Klaviyo Event Analytics Functions
    "getEventCounts": "POST",
    "getEmailEventRatios": "POST",
    "getTopClickedUrls": "POST",
    "getCampaignReasoning": "POST",
    "getEventLogSlice": "POST"
}
```

### 3. Function Definitions

The functions are defined in `app/routes/chat.py` with proper parameter schemas:

- **getEventCounts**: Requires `start_date` and `end_date` in YYYY-MM-DD format
- **getEmailEventRatios**: Requires `start_date` and `end_date` in YYYY-MM-DD format
- **getTopClickedUrls**: Requires `start_date` and `end_date`, optional `limit` (1-20)
- **getCampaignReasoning**: Requires `start_date` and `end_date` in ISO 8601 format, optional `campaign_id`
- **getEventLogSlice**: Requires `start_date` and `end_date`, optional `event_type`, `email`, and `limit`

### 4. System Message Updates

The AI system message has been updated to include:

- Description of available Klaviyo functions
- Parameter requirements and formats
- Usage guidelines for email analytics and campaign insights

## API Endpoints

The edge functions are accessible through the Supabase Edge Functions platform at:

```
https://roovzqstfwpvvybejjss.supabase.co/functions/v1/
```

### Available Endpoints:

- `POST /get-event-counts` - Event counts by type
- `POST /get-email-click-ratio` - Email engagement ratios
- `POST /get-top-clicked-urls` - Top clicked URLs
- `POST /campaign_reasoning` - Campaign reasoning and trends
- `POST /get-event-log-slice` - Filtered event log data

## Usage Examples

### Get Event Counts
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

### Get Email Engagement Ratios
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

### Get Top Clicked URLs
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "limit": 5
}
```

### Get Campaign Reasoning
```json
{
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-01-31T23:59:59Z",
  "campaign_id": "optional_campaign_id"
}
```

### Get Event Log Slice
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "event_type": "Clicked Email",
  "email": "user@example.com",
  "limit": 20
}
```

## Authentication

All edge function calls require the Supabase API key and are authenticated through the existing authentication system.

## Error Handling

The integration includes comprehensive error handling for:
- Network timeouts
- Invalid responses
- Authentication failures
- Parameter validation errors

## Testing

To test the integration:

1. Ensure the Supabase edge functions are deployed and accessible
2. Use the chat interface to ask questions about email analytics
3. Monitor the console logs for API call details
4. Verify that the AI correctly identifies and calls the appropriate functions

## Future Enhancements

Potential improvements:
- Add caching for frequently requested data
- Implement rate limiting for edge function calls
- Add metrics and monitoring for function performance
- Support for real-time event streaming
