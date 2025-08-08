"""
ARC Validation Module

Provides validation utilities for ARC protocol requests, responses, and data structures.
Uses JSON Schema for validation with detailed error reporting.
"""

import json
import logging
from typing import Dict, Any, Optional, Union, Type, List

from ..exceptions import (
    InvalidRequestError, ParseError, InvalidParamsError, ValidationError
)


logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a validation operation"""
    
    def __init__(self, is_valid: bool, errors: Optional[list] = None, data: Any = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.data = data
    
    def __bool__(self):
        return self.is_valid
    
    @property
    def error_message(self) -> str:
        """Get formatted error message"""
        if not self.errors:
            return ""
        return "; ".join(str(error) for error in self.errors)


def validate_arc_request(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate an ARC protocol request structure.
    
    Args:
        data: Raw request data dictionary
        
    Returns:
        ValidationResult with parsed request or errors
    """
    errors = []
    
    # Check if data is a dictionary
    if not isinstance(data, dict):
        return ValidationResult(False, errors=["Request must be a JSON object"])
    
    # Check required fields
    required_fields = ["arc", "id", "method", "requestAgent", "targetAgent", "params"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    # Check ARC version
    if data["arc"] != "1.0":
        errors.append(f"Unsupported ARC version: {data['arc']}")
    
    # Check id type
    if not isinstance(data["id"], (str, int)):
        errors.append("'id' must be a string or number")
    
    # Check method type
    if not isinstance(data["method"], str):
        errors.append("'method' must be a string")
    
    # Check agent fields
    if not isinstance(data["requestAgent"], str):
        errors.append("'requestAgent' must be a string")
    
    if not isinstance(data["targetAgent"], str):
        errors.append("'targetAgent' must be a string")
    
    # Check params type
    if not isinstance(data["params"], dict):
        errors.append("'params' must be an object")
    
    # Check traceId if present
    if "traceId" in data and not isinstance(data["traceId"], str):
        errors.append("'traceId' must be a string")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=data)


def validate_arc_response(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate an ARC protocol response structure.
    
    Args:
        data: Raw response data dictionary
        
    Returns:
        ValidationResult with parsed response or errors
    """
    errors = []
    
    # Check if data is a dictionary
    if not isinstance(data, dict):
        return ValidationResult(False, errors=["Response must be a JSON object"])
    
    # Check required fields
    required_fields = ["arc", "id", "responseAgent", "targetAgent"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    # Check ARC version
    if data["arc"] != "1.0":
        errors.append(f"Unsupported ARC version: {data['arc']}")
    
    # Check id type
    if not isinstance(data["id"], (str, int)):
        errors.append("'id' must be a string or number")
    
    # Check agent fields
    if not isinstance(data["responseAgent"], str):
        errors.append("'responseAgent' must be a string")
    
    if not isinstance(data["targetAgent"], str):
        errors.append("'targetAgent' must be a string")
    
    # Check result and error
    if "result" not in data and "error" not in data:
        errors.append("Response must contain either 'result' or 'error'")
    
    if "result" in data and "error" in data and data["result"] is not None and data["error"] is not None:
        errors.append("Response cannot contain both 'result' and 'error'")
    
    # Check error format if present
    if "error" in data and data["error"] is not None:
        if not isinstance(data["error"], dict):
            errors.append("'error' must be an object")
        else:
            error_obj = data["error"]
            if "code" not in error_obj:
                errors.append("Error object must contain 'code'")
            elif not isinstance(error_obj["code"], int):
                errors.append("Error code must be an integer")
                
            if "message" not in error_obj:
                errors.append("Error object must contain 'message'")
            elif not isinstance(error_obj["message"], str):
                errors.append("Error message must be a string")
    
    # Check traceId if present
    if "traceId" in data and not isinstance(data["traceId"], str):
        errors.append("'traceId' must be a string")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=data)


def validate_task_create_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate task.create method parameters"""
    errors = []
    
    # Check required fields
    if "initialMessage" not in params:
        errors.append("Missing required field: initialMessage")
    
    # Validate initialMessage if present
    if "initialMessage" in params:
        message_result = validate_message(params["initialMessage"])
        if not message_result:
            errors.extend(message_result.errors)
    
    # Check optional fields
    if "priority" in params:
        valid_priorities = ["LOW", "NORMAL", "HIGH", "URGENT"]
        if params["priority"] not in valid_priorities:
            errors.append(f"Invalid priority: {params['priority']}. Must be one of {', '.join(valid_priorities)}")
    
    if "metadata" in params and not isinstance(params["metadata"], dict):
        errors.append("metadata must be an object")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_task_send_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate task.send method parameters"""
    errors = []
    
    # Check required fields
    required_fields = ["taskId", "message"]
    for field in required_fields:
        if field not in params:
            errors.append(f"Missing required field: {field}")
    
    # Validate taskId
    if "taskId" in params and not isinstance(params["taskId"], str):
        errors.append("taskId must be a string")
    
    # Validate message
    if "message" in params:
        message_result = validate_message(params["message"])
        if not message_result:
            errors.extend(message_result.errors)
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_task_get_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate task.get method parameters"""
    errors = []
    
    # Check required fields
    if "taskId" not in params:
        errors.append("Missing required field: taskId")
    elif not isinstance(params["taskId"], str):
        errors.append("taskId must be a string")
    
    # Check optional fields
    if "includeMessages" in params and not isinstance(params["includeMessages"], bool):
        errors.append("includeMessages must be a boolean")
    
    if "includeArtifacts" in params and not isinstance(params["includeArtifacts"], bool):
        errors.append("includeArtifacts must be a boolean")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_task_cancel_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate task.cancel method parameters"""
    errors = []
    
    # Check required fields
    if "taskId" not in params:
        errors.append("Missing required field: taskId")
    elif not isinstance(params["taskId"], str):
        errors.append("taskId must be a string")
    
    # Check optional fields
    if "reason" in params and not isinstance(params["reason"], str):
        errors.append("reason must be a string")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_task_subscribe_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate task.subscribe method parameters"""
    errors = []
    
    # Check required fields
    required_fields = ["taskId", "callbackUrl"]
    for field in required_fields:
        if field not in params:
            errors.append(f"Missing required field: {field}")
    
    # Validate fields
    if "taskId" in params and not isinstance(params["taskId"], str):
        errors.append("taskId must be a string")
    
    if "callbackUrl" in params and not isinstance(params["callbackUrl"], str):
        errors.append("callbackUrl must be a string")
    
    # Validate events if present
    if "events" in params:
        if not isinstance(params["events"], list):
            errors.append("events must be an array")
        else:
            valid_events = [
                "TASK_CREATED", "TASK_STARTED", "TASK_PAUSED", 
                "TASK_RESUMED", "TASK_COMPLETED", "TASK_FAILED", 
                "TASK_CANCELED", "NEW_MESSAGE", "NEW_ARTIFACT", 
                "STATUS_CHANGE"
            ]
            for event in params["events"]:
                if event not in valid_events:
                    errors.append(f"Invalid event: {event}")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_stream_start_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate stream.start method parameters"""
    errors = []
    
    # Check required fields
    if "initialMessage" not in params:
        errors.append("Missing required field: initialMessage")
    
    # Validate initialMessage if present
    if "initialMessage" in params:
        message_result = validate_message(params["initialMessage"])
        if not message_result:
            errors.extend(message_result.errors)
    
    # Check optional fields
    if "metadata" in params and not isinstance(params["metadata"], dict):
        errors.append("metadata must be an object")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_stream_message_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate stream.message method parameters"""
    errors = []
    
    # Check required fields
    required_fields = ["streamId", "message"]
    for field in required_fields:
        if field not in params:
            errors.append(f"Missing required field: {field}")
    
    # Validate streamId
    if "streamId" in params and not isinstance(params["streamId"], str):
        errors.append("streamId must be a string")
    
    # Validate message
    if "message" in params:
        message_result = validate_message(params["message"])
        if not message_result:
            errors.extend(message_result.errors)
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_stream_end_params(params: Dict[str, Any]) -> ValidationResult:
    """Validate stream.end method parameters"""
    errors = []
    
    # Check required fields
    if "streamId" not in params:
        errors.append("Missing required field: streamId")
    elif not isinstance(params["streamId"], str):
        errors.append("streamId must be a string")
    
    # Check optional fields
    if "reason" in params and not isinstance(params["reason"], str):
        errors.append("reason must be a string")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=params)


def validate_message(data: Dict[str, Any]) -> ValidationResult:
    """
    Validate a message object.
    
    Args:
        data: Message data dictionary
        
    Returns:
        ValidationResult with validation result
    """
    errors = []
    
    # Check if data is a dictionary
    if not isinstance(data, dict):
        return ValidationResult(False, errors=["Message must be an object"])
    
    # Check required fields
    required_fields = ["role", "parts"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field in message: {field}")
    
    if errors:
        return ValidationResult(False, errors=errors)
    
    # Validate role
    valid_roles = ["user", "agent", "system"]
    if data["role"] not in valid_roles:
        errors.append(f"Invalid role: {data['role']}. Must be one of: {', '.join(valid_roles)}")
    
    # Validate parts
    if not isinstance(data["parts"], list):
        errors.append("Message parts must be an array")
    elif len(data["parts"]) == 0:
        errors.append("Message parts array cannot be empty")
    else:
        for i, part in enumerate(data["parts"]):
            if not isinstance(part, dict):
                errors.append(f"Part at index {i} must be an object")
                continue
                
            if "type" not in part:
                errors.append(f"Part at index {i} is missing required field: type")
            else:
                valid_types = ["TextPart", "DataPart", "FilePart", "ImagePart", "AudioPart"]
                if part["type"] not in valid_types:
                    errors.append(f"Invalid part type at index {i}: {part['type']}. Must be one of: {', '.join(valid_types)}")
            
            # Check content based on type
            if "type" in part and part["type"] == "TextPart":
                if "content" not in part:
                    errors.append(f"TextPart at index {i} is missing required field: content")
                elif not isinstance(part["content"], str):
                    errors.append(f"TextPart content at index {i} must be a string")
            
    if errors:
        return ValidationResult(False, errors=errors)
    
    return ValidationResult(True, data=data)


def validate_method_params(method: str, params: Any) -> ValidationResult:
    """
    Validate method parameters for specific ARC methods.
    
    Args:
        method: Method name
        params: Method parameters
        
    Returns:
        ValidationResult with validation result
    """
    # Handle null params
    if params is None:
        return ValidationResult(False, errors=["Method parameters cannot be null"])
    
    # Check params is an object
    if not isinstance(params, dict):
        return ValidationResult(False, errors=["Method parameters must be an object"])
    
    # Delegate to specific validators based on method
    if method == "task.create":
        return validate_task_create_params(params)
    elif method == "task.send":
        return validate_task_send_params(params)
    elif method == "task.get":
        return validate_task_get_params(params)
    elif method == "task.cancel":
        return validate_task_cancel_params(params)
    elif method == "task.subscribe":
        return validate_task_subscribe_params(params)
    elif method == "stream.start":
        return validate_stream_start_params(params)
    elif method == "stream.message":
        return validate_stream_message_params(params)
    elif method == "stream.end":
        return validate_stream_end_params(params)
    else:
        # For unknown methods, just check it's an object
        # Implementations may have custom methods
        return ValidationResult(True, data=params)


class RequestValidator:
    """
    Validator for ARC protocol requests.
    Can be used as middleware in ARC server.
    """
    
    def __init__(self, strict: bool = True):
        """
        Initialize validator.
        
        Args:
            strict: If True, reject requests with any validation errors
                   If False, log warnings but allow processing
        """
        self.strict = strict
    
    async def __call__(self, request: Dict[str, Any], context: Dict[str, Any]) -> None:
        """
        Validate an ARC request.
        
        Args:
            request: Raw request data
            context: Request context
            
        Raises:
            InvalidRequestError: If request validation fails and strict mode is on
        """
        # Validate ARC request structure
        result = validate_arc_request(request)
        if not result:
            logger.warning(f"ARC request validation failed: {result.error_message}")
            if self.strict:
                raise InvalidRequestError(result.error_message)
        
        # Validate method params if structure is valid
        if result:
            method = request["method"]
            params = request["params"]
            params_result = validate_method_params(method, params)
            
            if not params_result:
                logger.warning(f"Method params validation failed for {method}: {params_result.error_message}")
                if self.strict:
                    raise InvalidParamsError(params_result.error_message)


def validate_request(data: Dict[str, Any]) -> bool:
    """
    Simple helper to validate an ARC request.
    
    Args:
        data: Request data
        
    Returns:
        True if valid, False otherwise
    """
    return bool(validate_arc_request(data))


def validate_response(data: Dict[str, Any]) -> bool:
    """
    Simple helper to validate an ARC response.
    
    Args:
        data: Response data
        
    Returns:
        True if valid, False otherwise
    """
    return bool(validate_arc_response(data))