"""
ARC Protocol Models

Generated models for ARC protocol requests, responses, and data structures.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Set

from pydantic import AnyUrl, BaseModel, Field, RootModel


# === Enum Types ===

class Role(Enum):
    """Message role (user, agent, or system)"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class PartType(Enum):
    """Message part type"""
    TEXT_PART = "TextPart"
    DATA_PART = "DataPart"
    FILE_PART = "FilePart"
    IMAGE_PART = "ImagePart"
    AUDIO_PART = "AudioPart"


class Encoding(Enum):
    """Data encoding type"""
    BASE64 = "base64"
    UTF8 = "utf8"
    BINARY = "binary"


class TaskStatus(Enum):
    """Task status values"""
    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class ChatStatus(Enum):
    """Chat status values"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class Priority(Enum):
    """Task priority levels"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class EventType(Enum):
    """Task notification event types"""
    TASK_CREATED = "TASK_CREATED"
    TASK_STARTED = "TASK_STARTED"
    TASK_PAUSED = "TASK_PAUSED"
    TASK_RESUMED = "TASK_RESUMED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELED = "TASK_CANCELED"
    NEW_MESSAGE = "NEW_MESSAGE"
    NEW_ARTIFACT = "NEW_ARTIFACT"
    STATUS_CHANGE = "STATUS_CHANGE"


class ResultType(Enum):
    """Result type indicator"""
    TASK = "task"
    CHAT = "chat"
    SUCCESS = "success"
    SUBSCRIPTION = "subscription"


# === Base Models ===

class Part(BaseModel):
    """
    Message part containing text or binary content.
    Parts are used to represent different types of content in messages.
    """
    type: PartType
    content: Optional[Any] = Field(
        None, description="Text content or data payload"
    )
    mime_type: Optional[str] = Field(
        None, alias="mimeType", description="MIME type for data/file parts"
    )
    filename: Optional[str] = Field(
        None, description="Original filename for file parts"
    )
    size: Optional[int] = Field(
        None, description="Size in bytes for data/file parts"
    )
    encoding: Optional[Encoding] = Field(
        None, description="Encoding for data parts"
    )
    
    class Config:
        populate_by_name = True
        extra = "allow"


class Message(BaseModel):
    """
    Message object containing content from a user, agent, or system.
    Messages are exchanged between agents and can contain multiple parts.
    """
    role: Role
    parts: List[Part] = Field(..., min_length=1)
    timestamp: Optional[datetime] = None
    agent_id: Optional[str] = Field(
        None, alias="agentId", description="ID of agent that sent this message"
    )
    
    class Config:
        populate_by_name = True


class Artifact(BaseModel):
    """
    Artifact generated during task execution.
    Artifacts represent outputs, files, or data produced by agents.
    """
    artifact_id: str = Field(
        ..., alias="artifactId", description="Unique identifier for artifact"
    )
    name: str = Field(..., description="Human-readable artifact name")
    description: Optional[str] = Field(
        None, description="Description of artifact contents/purpose"
    )
    parts: List[Part]
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    created_by: Optional[str] = Field(
        None, alias="createdBy", description="Agent ID that created this artifact"
    )
    version: Optional[str] = Field(None, description="Artifact version number")
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class TaskObject(BaseModel):
    """
    Task object representing an asynchronous agent task.
    Tasks are long-running operations that may require multiple interactions.
    """
    task_id: str = Field(
        ..., alias="taskId", description="Unique identifier for the task"
    )
    status: TaskStatus
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    assigned_agent: Optional[str] = Field(
        None, alias="assignedAgent", description="ID of agent processing this task"
    )
    messages: Optional[List[Message]] = Field(
        None, description="Conversation history for this task"
    )
    artifacts: Optional[List[Artifact]] = Field(
        None, description="Files, data, or outputs generated during task execution"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Custom task metadata"
    )
    
    class Config:
        populate_by_name = True


class ChatObject(BaseModel):
    """
    Chat object representing a real-time communication session.
    Chats are used for interactive, real-time conversations.
    """
    chat_id: str = Field(
        ..., alias="chatId", description="Unique identifier for the chat"
    )
    status: ChatStatus
    message: Optional[Message] = Field(
        None, description="Latest message in the chat"
    )
    participants: Optional[List[str]] = Field(
        None, description="List of participants in the chat"
    )
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    closed_at: Optional[datetime] = Field(
        None, alias="closedAt", description="When the chat was closed"
    )
    reason: Optional[str] = Field(
        None, description="Reason for closing the chat"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Custom chat metadata"
    )
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class SubscriptionObject(BaseModel):
    """
    Subscription for task notifications.
    Subscriptions allow receiving webhooks when task status changes.
    """
    subscription_id: str = Field(..., alias="subscriptionId")
    task_id: str = Field(..., alias="taskId")
    callback_url: AnyUrl = Field(..., alias="callbackUrl")
    events: List[EventType]
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    active: Optional[bool] = True
    
    class Config:
        populate_by_name = True


class ErrorObject(BaseModel):
    """
    Error information for failed requests.
    """
    code: int = Field(
        ..., description="Error code (negative integer)"
    )
    message: str = Field(
        ..., description="Human-readable error message"
    )
    details: Optional[Any] = Field(
        None, description="Additional error details"
    )
    
    class Config:
        populate_by_name = True


# === Method Parameter Models ===

class TaskCreateParams(BaseModel):
    """
    Parameters for task.create method.
    Used to create a new asynchronous task.
    """
    initial_message: Message = Field(..., alias="initialMessage")
    priority: Optional[Priority] = Priority.NORMAL
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class TaskSendParams(BaseModel):
    """
    Parameters for task.send method.
    Used to send a message to an existing task.
    """
    task_id: str = Field(..., alias="taskId")
    message: Message
    
    class Config:
        populate_by_name = True


class TaskInfoParams(BaseModel):
    """
    Parameters for task.info method.
    Used to retrieve task status and history.
    """
    task_id: str = Field(..., alias="taskId")
    include_messages: Optional[bool] = Field(True, alias="includeMessages")
    include_artifacts: Optional[bool] = Field(True, alias="includeArtifacts")
    
    class Config:
        populate_by_name = True


class TaskCancelParams(BaseModel):
    """
    Parameters for task.cancel method.
    Used to cancel an existing task.
    """
    task_id: str = Field(..., alias="taskId")
    reason: Optional[str] = Field(None, description="Reason for cancellation")
    
    class Config:
        populate_by_name = True


class TaskSubscribeParams(BaseModel):
    """
    Parameters for task.subscribe method.
    Used to subscribe to task notifications via webhook.
    """
    task_id: str = Field(..., alias="taskId")
    callback_url: AnyUrl = Field(
        ..., alias="callbackUrl", description="Webhook URL for task notifications"
    )
    events: Optional[List[EventType]] = Field(
        None, description="Events to subscribe to (default: TASK_COMPLETED, TASK_FAILED)"
    )
    
    class Config:
        populate_by_name = True


class TaskNotificationParams(BaseModel):
    """
    Parameters for task.notification method.
    Used to send notifications about task status changes.
    """
    task_id: str = Field(..., alias="taskId")
    event: EventType
    timestamp: datetime
    data: Dict[str, Any] = Field(
        ..., description="Event-specific notification data"
    )
    
    class Config:
        populate_by_name = True


class ChatStartParams(BaseModel):
    """
    Parameters for chat.start method.
    Used to start a real-time conversation chat.
    """
    initial_message: Message = Field(..., alias="initialMessage")
    chat_id: Optional[str] = Field(None, alias="chatId")
    stream: Optional[bool] = False
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class ChatMessageParams(BaseModel):
    """
    Parameters for chat.message method.
    Used to send a message to an active chat.
    """
    chat_id: str = Field(..., alias="chatId")
    message: Message
    stream: Optional[bool] = False
    
    class Config:
        populate_by_name = True


class ChatEndParams(BaseModel):
    """
    Parameters for chat.end method.
    Used to end an active chat.
    """
    chat_id: str = Field(..., alias="chatId")
    reason: Optional[str] = Field(None, description="Reason for ending chat")
    
    class Config:
        populate_by_name = True



    
    class Config:
        populate_by_name = True


# === Result Models ===

class TaskResult(BaseModel):
    """
    Result containing task data.
    Returned by task-related methods.
    """
    type: ResultType = ResultType.TASK
    task: TaskObject
    
    class Config:
        populate_by_name = True


class ChatResult(BaseModel):
    """
    Result containing chat data.
    Returned by chat-related methods.
    """
    type: ResultType = ResultType.CHAT
    chat: ChatObject
    
    class Config:
        populate_by_name = True


class SubscriptionResult(BaseModel):
    """
    Result containing subscription data.
    Returned by task.subscribe method.
    """
    type: ResultType = ResultType.SUBSCRIPTION
    subscription: SubscriptionObject
    
    class Config:
        populate_by_name = True


class SuccessResult(BaseModel):
    """
    Simple success result.
    Returned by methods that don't need to return specific data.
    """
    success: bool = True
    message: Optional[str] = Field(
        None, description="Success message for simple operations"
    )
    
    class Config:
        populate_by_name = True


# Combined result type for all possible results
MethodResult = Union[TaskResult, ChatResult, SubscriptionResult, SuccessResult]


# === Request/Response Models ===

class ARCRequest(BaseModel):
    """
    ARC protocol request.
    All ARC requests follow this structure.
    """
    arc: str = "1.0"
    id: Union[str, int] = Field(..., description="Unique request identifier")
    method: str = Field(..., description="Method to invoke")
    request_agent: str = Field(
        ..., alias="requestAgent", description="ID of the agent sending the request"
    )
    target_agent: str = Field(
        ..., alias="targetAgent", description="ID of the agent that should handle the request"
    )
    params: Dict[str, Any] = Field(..., description="Method-specific parameters")
    trace_id: Optional[str] = Field(
        None, alias="traceId", description="Workflow tracking ID for multi-agent processes"
    )
    
    class Config:
        populate_by_name = True


class ARCResponse(BaseModel):
    """
    ARC protocol response.
    All ARC responses follow this structure.
    """
    arc: str = "1.0"
    id: Union[str, int] = Field(..., description="Matches request ID")
    response_agent: str = Field(
        ..., alias="responseAgent", description="ID of the agent that processed the request"
    )
    target_agent: str = Field(
        ..., alias="targetAgent", description="ID of the agent that should receive the response"
    )
    result: Optional[Dict[str, Any]] = Field(
        None, description="Method result data (null if error)"
    )
    error: Optional[ErrorObject] = Field(
        None, description="Error information (null if successful)"
    )
    trace_id: Optional[str] = Field(
        None, alias="traceId", description="Same workflow tracking ID from request"
    )
    
    class Config:
        populate_by_name = True