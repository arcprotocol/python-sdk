"""
ARC Logging Utilities

Provides enhanced logging facilities for ARC protocol communication.
Includes structured logging, correlation IDs, and request/response logging.
"""

import json
import logging
import sys
import uuid
from typing import Dict, Any, Optional, Union
from datetime import datetime

# Constants for log levels
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Default log format
DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Default JSON log format
DEFAULT_JSON_FORMAT = {
    "timestamp": "%(asctime)s",
    "level": "%(levelname)s",
    "logger": "%(name)s",
    "message": "%(message)s",
    "file": "%(pathname)s",
    "line": "%(lineno)d",
    "function": "%(funcName)s"
}


class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds context to log records.
    
    Allows adding trace IDs, request IDs, agent IDs, and other
    metadata to log messages for correlation.
    """
    
    def __init__(self, logger, extra=None):
        """
        Initialize adapter with logger and optional extra context.
        
        Args:
            logger: Base logger instance
            extra: Optional dictionary with context values
        """
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        """
        Process log record to add context.
        
        Args:
            msg: Log message
            kwargs: Logging keyword arguments
            
        Returns:
            Tuple of (msg, kwargs) with context added
        """
        # Add context to the extra dict if not already there
        kwargs_copy = kwargs.copy()
        extra = kwargs_copy.get("extra", {}).copy()
        
        # Add adapter's extra to the log record's extra
        for key, value in self.extra.items():
            if key not in extra:
                extra[key] = value
        
        # Update kwargs with merged extra
        kwargs_copy["extra"] = extra
        return msg, kwargs_copy
    
    def bind(self, **kwargs):
        """
        Create a new adapter with additional context.
        
        Args:
            **kwargs: Additional context to bind
            
        Returns:
            New ContextAdapter with merged context
        """
        new_extra = {**self.extra, **kwargs}
        return ContextAdapter(self.logger, new_extra)


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Formats log records as JSON objects with consistent schema
    for easier parsing and analysis.
    """
    
    def __init__(self, fmt=None, datefmt=None, style='%', json_default=str):
        """
        Initialize JSON formatter.
        
        Args:
            fmt: Format dictionary or None for default
            datefmt: Date format string
            style: Format string style (%, {, or $)
            json_default: Default JSON serializer for non-serializable objects
        """
        super().__init__(None, datefmt, style)
        self.fmt = fmt or DEFAULT_JSON_FORMAT
        self.json_default = json_default
    
    def format(self, record):
        """
        Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation of the log record
        """
        # Start with the format template
        log_data = {}
        for key, value in self.fmt.items():
            log_data[key] = self._format_value(value, record)
        
        # Add extra fields from the record
        if hasattr(record, "arc_context") and record.arc_context:
            log_data["context"] = record.arc_context
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields
        extras = {}
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and key not in ["arc_context", "message"]:
                try:
                    extras[key] = value
                except (TypeError, ValueError):
                    extras[key] = str(value)
        
        if extras:
            log_data["extra"] = extras
        
        return json.dumps(log_data, default=self.json_default)
    
    def _format_value(self, fmt_string, record):
        """
        Format a value using the record.
        
        Args:
            fmt_string: Format string
            record: Log record
            
        Returns:
            Formatted value
        """
        if not fmt_string:
            return None
            
        # Use default formatter to handle standard format strings
        formatter = logging.Formatter(fmt_string)
        return formatter.format(record)


def create_logger(
    name: str = "arc",
    level: int = logging.INFO,
    json_format: bool = False,
    include_timestamps: bool = True,
    handler: Optional[logging.Handler] = None,
    propagate: bool = False
) -> ContextAdapter:
    """
    Create a logger with the specified configuration.
    
    Args:
        name: Logger name
        level: Logging level
        json_format: Whether to use JSON formatting
        include_timestamps: Whether to include timestamps in logs
        handler: Optional handler to use instead of default
        propagate: Whether to propagate to parent logger
        
    Returns:
        Configured logger wrapped in ContextAdapter
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = propagate
    
    # Remove existing handlers
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    
    # Create handler if not provided
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
    
    # Configure formatter
    if json_format:
        fmt = DEFAULT_JSON_FORMAT
        if not include_timestamps:
            fmt.pop("timestamp", None)
        formatter = JsonFormatter(fmt)
    else:
        if include_timestamps:
            formatter = logging.Formatter(DEFAULT_FORMAT)
        else:
            formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Wrap with context adapter
    return ContextAdapter(logger, {"logger_name": name})


def get_logger(
    name: str = "arc",
    level: Optional[int] = None
) -> ContextAdapter:
    """
    Get or create a logger with the specified name.
    
    Args:
        name: Logger name
        level: Optional level override
        
    Returns:
        Logger wrapped in ContextAdapter
    """
    logger = logging.getLogger(name)
    
    # Set level if provided
    if level is not None:
        logger.setLevel(level)
    
    # Check if the logger already has handlers
    if not logger.handlers and not logger.propagate:
        # Add a basic handler if no handlers exist and not propagating
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(DEFAULT_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return ContextAdapter(logger)


def configure_root_logger(
    level: int = logging.INFO,
    json_format: bool = False,
    include_timestamps: bool = True,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure the root logger.
    
    Args:
        level: Logging level
        json_format: Whether to use JSON formatting
        include_timestamps: Whether to include timestamps
        log_file: Optional file to log to
        
    Returns:
        Configured root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    
    # Create handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    handlers.append(console_handler)
    
    # File handler if requested
    if log_file:
        file_handler = logging.FileHandler(log_file)
        handlers.append(file_handler)
    
    # Configure formatters and add handlers
    for handler in handlers:
        if json_format:
            fmt = DEFAULT_JSON_FORMAT
            if not include_timestamps:
                fmt.pop("timestamp", None)
            formatter = JsonFormatter(fmt)
        else:
            if include_timestamps:
                formatter = logging.Formatter(DEFAULT_FORMAT)
            else:
                formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    
    return root_logger


def log_request(
    logger: Union[logging.Logger, ContextAdapter],
    request: Dict[str, Any],
    level: int = logging.DEBUG
) -> None:
    """
    Log an ARC request.
    
    Args:
        logger: Logger to use
        request: ARC request object
        level: Logging level
    """
    request_id = request.get("id", "unknown")
    method = request.get("method", "unknown")
    request_agent = request.get("requestAgent", "unknown")
    target_agent = request.get("targetAgent", "unknown")
    trace_id = request.get("traceId", "none")
    
    # Redact sensitive information from the request
    request_copy = request.copy()
    _redact_sensitive_data(request_copy)
    
    # Format the log message
    message = f"ARC Request: {method} from {request_agent} to {target_agent}"
    context = {
        "request_id": request_id,
        "method": method,
        "request_agent": request_agent,
        "target_agent": target_agent,
        "trace_id": trace_id,
        "request": request_copy
    }
    
    # Log with context
    if isinstance(logger, ContextAdapter):
        logger.bind(**context).log(level, message)
    else:
        logger.log(level, message, extra={"arc_context": context})


def log_response(
    logger: Union[logging.Logger, ContextAdapter],
    response: Dict[str, Any],
    level: int = logging.DEBUG
) -> None:
    """
    Log an ARC response.
    
    Args:
        logger: Logger to use
        response: ARC response object
        level: Logging level
    """
    response_id = response.get("id", "unknown")
    response_agent = response.get("responseAgent", "unknown")
    target_agent = response.get("targetAgent", "unknown")
    trace_id = response.get("traceId", "none")
    
    # Check if response has error
    has_error = bool(response.get("error"))
    status = "ERROR" if has_error else "SUCCESS"
    
    # Adjust log level based on response status
    if has_error and level <= logging.INFO:
        level = logging.WARNING
    
    # Redact sensitive information from the response
    response_copy = response.copy()
    _redact_sensitive_data(response_copy)
    
    # Format the log message
    message = f"ARC Response: {status} from {response_agent} to {target_agent}"
    context = {
        "response_id": response_id,
        "response_agent": response_agent,
        "target_agent": target_agent,
        "trace_id": trace_id,
        "status": status,
        "response": response_copy
    }
    
    # Log with context
    if isinstance(logger, ContextAdapter):
        logger.bind(**context).log(level, message)
    else:
        logger.log(level, message, extra={"arc_context": context})


def _redact_sensitive_data(data: Dict[str, Any]) -> None:
    """
    Redact sensitive data in-place from request/response objects.
    
    Args:
        data: Data object to redact
    """
    if not isinstance(data, dict):
        return
    
    # Fields that might contain sensitive information
    sensitive_fields = [
        "token", "password", "secret", "key", "auth", "credential",
        "authorization", "apiKey"
    ]
    
    # Redact sensitive fields at the top level
    for field in list(data.keys()):
        if any(sensitive in field.lower() for sensitive in sensitive_fields):
            data[field] = "*** REDACTED ***"
        elif isinstance(data[field], dict):
            _redact_sensitive_data(data[field])
        elif isinstance(data[field], list):
            for item in data[field]:
                if isinstance(item, dict):
                    _redact_sensitive_data(item)
    
    # Special handling for params
    if "params" in data and isinstance(data["params"], dict):
        _redact_sensitive_data(data["params"])


def create_correlation_id() -> str:
    """
    Create a unique correlation ID for request tracing.
    
    Returns:
        Unique ID string
    """
    return f"cid-{uuid.uuid4().hex[:16]}"


def create_trace_id() -> str:
    """
    Create a unique trace ID for workflow tracing.
    
    Returns:
        Unique ID string
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]
    return f"trace-{timestamp}-{random_suffix}"