from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Dict, Any, Callable, Awaitable
import time
import logging
from collections import defaultdict
import asyncio
from config import RATE_LIMIT, ADMINS

logger = logging.getLogger(__name__)

class RateLimiter(BaseMiddleware):
    """
    Middleware for rate limiting user requests to prevent abuse and server overload
    """
    def __init__(self):
        self.user_requests = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Extract user ID from the event
        user_id = None
        if hasattr(event, "from_user") and event.from_user:
            user_id = event.from_user.id
        elif hasattr(event, "chat") and event.chat:
            user_id = event.chat.id
        
        if not user_id:
            # If we can't identify the user, just process the request
            return await handler(event, data)
        
        # Determine rate limit based on whether user is admin
        limit_config = RATE_LIMIT["admin"] if user_id in ADMINS else RATE_LIMIT["default"]
        max_requests = limit_config["requests"]
        time_window = limit_config["per_seconds"]
        
        # Get current time
        current_time = time.time()
        
        # Clean up old requests and check if rate limit exceeded
        is_limited = False
        
        async with self.lock:
            # Remove requests older than the time window
            self.user_requests[user_id] = [
                req_time for req_time in self.user_requests[user_id]
                if current_time - req_time < time_window
            ]
            
            # Check if the user has exceeded the rate limit
            if len(self.user_requests[user_id]) >= max_requests:
                is_limited = True
            else:
                # Add current request to the list
                self.user_requests[user_id].append(current_time)
        
        if is_limited:
            # User has exceeded rate limit
            logger.warning(f"Rate limit exceeded for user {user_id}")
            
            # If this is a message, respond with a rate limit message
            if hasattr(event, "answer"):
                try:
                    await event.answer(
                        "You are sending too many requests. Please wait a moment before trying again.",
                        show_alert=True
                    )
                    return None
                except Exception as e:
                    logger.error(f"Error sending rate limit message: {e}")
            
            # For other types of events, just drop the request
            return None
        
        # Process the request normally
        return await handler(event, data)


class ErrorHandler(BaseMiddleware):
    """
    Middleware for handling errors in request processing
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Process the request
            return await handler(event, data)
        except Exception as e:
            # Log the error
            logger.error(f"Error processing request: {e}", exc_info=True)
            
            # Try to send an error message to the user
            try:
                if hasattr(event, "answer"):
                    await event.answer(
                        "Sorry, an error occurred while processing your request. Please try again later.",
                        show_alert=True
                    )
                elif hasattr(event, "message") and hasattr(event.message, "answer"):
                    await event.message.answer(
                        "Sorry, an error occurred while processing your request. Please try again later."
                    )
            except Exception as msg_error:
                logger.error(f"Error sending error message: {msg_error}")
            
            # Return None to prevent further processing
            return None
