"""
ARC Server Decorators

Provides decorators for ARC server method handlers:
- Method validation decorators
- Scope requirement decorators
- Error handling decorators
"""

import functools
import inspect
import logging
from typing import Callable, List, Dict, Any, Optional, Union, TypeVar, cast

from ..exceptions import (
    ARCException, InvalidParamsError, ARCTaskError, TaskNotFoundError,
    ARCChatError, ChatNotFoundError, InternalError
)


logger = logging.getLogger(__name__)
F = TypeVar('F', bound=Callable[..., Any])


def validate_params(schema: Any = None) -> Union[Callable[[F], F], F]:
    """
    Decorator to validate method parameters against a schema.
    
    Can be used with or without a schema:
        @validate_params(TaskCreateParamsModel)  # With schema
        @validate_params()                      # Without schema
        
    Args:
        schema: Pydantic model or callable validator
        
    Example:
        @validate_params(TaskCreateParamsModel)
        async def handle_task_create(params, context):
            # params is validated against TaskCreateParamsModel
    """
    # Handle case when decorator is used without parentheses
    if callable(schema) and not inspect.isclass(schema):
        func = schema
        schema = None
        
        @functools.wraps(func)
        async def direct_wrapper(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
            return await func(params, context)
        
        return cast(F, direct_wrapper)
    
    # Normal case with schema
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
            # Validate parameters if schema is provided
            if schema is not None:
                try:
                    if inspect.isclass(schema) and hasattr(schema, "model_validate"):
                        # Pydantic v2 model
                        validated_params = schema.model_validate(params)
                        params = validated_params.model_dump()
                    elif inspect.isclass(schema) and hasattr(schema, "parse_obj"):
                        # Pydantic v1 model
                        validated_params = schema.parse_obj(params)
                        params = validated_params.dict()
                    elif callable(schema):
                        # Custom validator function
                        validated_params = schema(params)
                        if validated_params is not None:
                            params = validated_params
                except Exception as e:
                    logger.error(f"Parameter validation failed: {str(e)}")
                    raise InvalidParamsError(f"Invalid parameters: {str(e)}")
            
            # Call the handler
            return await func(params, context)
        return cast(F, wrapper)
    return decorator


def require_scopes(required_scopes: List[str]) -> Callable[[F], F]:
    """
    Decorator to require specific OAuth2 scopes for a method handler.
    
    Args:
        required_scopes: List of required OAuth2 scopes
        
    Example:
        @require_scopes(["arc.task.controller", "arc.agent.caller"])
        async def handle_task_create(params, context):
            # Only accessible with these scopes
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
            # Extract scopes from context (set by auth middleware)
            provided_scopes = context.get("auth", {}).get("scopes", [])
            
            # Check if all required scopes are present
            if not set(required_scopes).issubset(set(provided_scopes)):
                from ..exceptions import InsufficientScopeError
                raise InsufficientScopeError(
                    required_scopes=required_scopes,
                    provided_scopes=provided_scopes,
                    message=f"Insufficient scope for {context.get('method')}"
                )
            
            # Call the handler
            return await func(params, context)
        return cast(F, wrapper)
    return decorator


def task_method(task_id_param: str = "taskId") -> Callable[[F], F]:
    """
    Decorator for task methods that validates the task ID exists.
    
    Args:
        task_id_param: Name of the task ID parameter (default: "taskId")
        
    Example:
        @task_method()
        async def handle_task_get(params, context):
            # Task ID is validated to exist
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
            # Validate task ID exists
            if task_id_param not in params:
                raise InvalidParamsError(f"Missing required parameter: {task_id_param}")
            
            task_id = params[task_id_param]
            
            # Additional task validation could be done here
            # For example, check if task exists in database
            
            # Call the handler
            return await func(params, context)
        return cast(F, wrapper)
    return decorator


def chat_method(chat_id_param: str = "chatId") -> Callable[[F], F]:
    """
    Decorator for chat methods that validates the chat ID exists.
    
    Args:
        chat_id_param: Name of the chat ID parameter (default: "chatId")
        
    Example:
        @chat_method()
        async def handle_chat_message(params, context):
            # Chat ID is validated to exist
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
            # Validate chat ID exists
            if chat_id_param not in params:
                raise InvalidParamsError(f"Missing required parameter: {chat_id_param}")
            
            chat_id = params[chat_id_param]
            
            # Additional chat validation could be done here
            # For example, check if chat exists and is active
            
            # Call the handler
            return await func(params, context)
        return cast(F, wrapper)
    return decorator


def error_handler(func: F) -> F:
    """
    Decorator for handling exceptions in method handlers.
    
    Catches exceptions and converts them to appropriate ARC error responses.
    
    Example:
        @error_handler
        async def handle_task_create(params, context):
            # Exceptions will be properly handled
    """
    @functools.wraps(func)
    async def wrapper(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        try:
            return await func(params, context)
        except ARCException:
            # Pass through ARC exceptions as-is
            raise
        except Exception as e:
            # Log unexpected errors and convert to InternalError
            logger.exception(f"Unexpected error in {context.get('method')} handler: {str(e)}")
            raise InternalError(f"Internal error: {str(e)}")
    return cast(F, wrapper)


def trace_method(func: F) -> F:
    """
    Decorator for adding trace logging to method handlers.
    
    Example:
        @trace_method
        async def handle_task_create(params, context):
            # Method execution will be traced with logs
    """
    @functools.wraps(func)
    async def wrapper(params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        method = context.get("method", "unknown")
        request_id = context.get("request_id", "unknown")
        trace_id = context.get("trace_id", "none")
        
        logger.info(
            f"Executing method {method} - "
            f"RequestID: {request_id}, TraceID: {trace_id}"
        )
        
        start_time = __import__("time").time()
        result = await func(params, context)
        duration_ms = round((__import__("time").time() - start_time) * 1000)
        
        logger.info(
            f"Completed method {method} in {duration_ms}ms - "
            f"RequestID: {request_id}, TraceID: {trace_id}"
        )
        
        return result
    return cast(F, wrapper)