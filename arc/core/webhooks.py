"""
ARC Webhooks Module

Provides webhooks functionality for ARC protocol notifications.
"""

import asyncio
import json
import logging
import uuid
import time
from typing import Dict, List, Any, Optional, Union, Callable, Set

import httpx

from ..exceptions import (
    NetworkError, ConnectionError, TimeoutError, ARCException
)


logger = logging.getLogger(__name__)


class Subscription:
    """
    Represents a webhook subscription to ARC events.
    """
    
    def __init__(
        self,
        subscription_id: str,
        task_id: str,
        callback_url: str,
        events: List[str],
        created_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize subscription.
        
        Args:
            subscription_id: Unique identifier for this subscription
            task_id: Task identifier being monitored
            callback_url: Webhook URL for event notifications
            events: List of events to subscribe to
            created_at: ISO timestamp when subscription was created
            metadata: Optional metadata for this subscription
        """
        self.subscription_id = subscription_id
        self.task_id = task_id
        self.callback_url = callback_url
        self.events = events
        self.created_at = created_at or self._get_timestamp()
        self.metadata = metadata or {}
        self.active = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert subscription to dictionary"""
        return {
            "subscriptionId": self.subscription_id,
            "taskId": self.task_id,
            "callbackUrl": self.callback_url,
            "events": self.events,
            "createdAt": self.created_at,
            "active": self.active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Subscription':
        """Create subscription from dictionary"""
        return cls(
            subscription_id=data["subscriptionId"],
            task_id=data["taskId"],
            callback_url=data["callbackUrl"],
            events=data["events"],
            created_at=data.get("createdAt"),
            metadata=data.get("metadata", {})
        )
    
    def should_notify(self, event: str) -> bool:
        """Check if this subscription should be notified of an event"""
        return self.active and (event in self.events or "STATUS_CHANGE" in self.events)
    
    def deactivate(self):
        """Deactivate this subscription"""
        self.active = False
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


class WebhookManager:
    """
    Manages webhook subscriptions and notifications for ARC tasks.
    
    Features:
    - Subscription management
    - Event delivery with retries
    - Signature verification
    - Subscription expiration
    """
    
    # Default retry settings
    DEFAULT_RETRY_ATTEMPTS = 3
    DEFAULT_RETRY_DELAY = 5.0  # seconds
    DEFAULT_TIMEOUT = 10.0  # seconds
    
    # Valid events
    VALID_EVENTS = [
        "TASK_CREATED",
        "TASK_STARTED",
        "TASK_PAUSED",
        "TASK_RESUMED",
        "TASK_COMPLETED",
        "TASK_FAILED",
        "TASK_CANCELED",
        "NEW_MESSAGE",
        "NEW_ARTIFACT",
        "STATUS_CHANGE"
    ]
    
    def __init__(
        self, 
        agent_id: str,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        webhook_timeout: float = DEFAULT_TIMEOUT,
        webhook_secret: Optional[str] = None
    ):
        """
        Initialize webhook manager.
        
        Args:
            agent_id: ID of this agent
            retry_attempts: Number of retry attempts for failed deliveries
            retry_delay: Delay between retry attempts in seconds
            webhook_timeout: Timeout for webhook requests in seconds
            webhook_secret: Secret for signing webhook payloads
        """
        self.agent_id = agent_id
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.webhook_timeout = webhook_timeout
        self.webhook_secret = webhook_secret
        
        # Subscription storage
        self.subscriptions: Dict[str, Subscription] = {}
        self.task_subscriptions: Dict[str, Set[str]] = {}
        
        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=webhook_timeout)
    
    async def close(self):
        """Close resources"""
        await self.http_client.aclose()
    
    def create_subscription(
        self, 
        task_id: str,
        callback_url: str,
        events: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Subscription:
        """
        Create a new webhook subscription.
        
        Args:
            task_id: Task identifier to monitor
            callback_url: Webhook URL for notifications
            events: List of events to subscribe to (default: TASK_COMPLETED and TASK_FAILED)
            metadata: Optional subscription metadata
            
        Returns:
            Created Subscription object
        """
        # Use default events if not provided
        if not events:
            events = ["TASK_COMPLETED", "TASK_FAILED"]
        
        # Validate events
        for event in events:
            if event not in self.VALID_EVENTS:
                raise ValueError(f"Invalid event: {event}")
        
        # Create subscription
        subscription_id = f"sub-{uuid.uuid4().hex[:8]}"
        subscription = Subscription(
            subscription_id=subscription_id,
            task_id=task_id,
            callback_url=callback_url,
            events=events,
            metadata=metadata
        )
        
        # Store subscription
        self.subscriptions[subscription_id] = subscription
        
        # Add to task index
        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = set()
        self.task_subscriptions[task_id].add(subscription_id)
        
        logger.info(f"Created subscription {subscription_id} for task {task_id}")
        return subscription
    
    def get_subscription(self, subscription_id: str) -> Subscription:
        """
        Get subscription by ID.
        
        Args:
            subscription_id: Subscription identifier
            
        Returns:
            Subscription object
            
        Raises:
            KeyError: If subscription does not exist
        """
        if subscription_id not in self.subscriptions:
            raise KeyError(f"Subscription not found: {subscription_id}")
        
        return self.subscriptions[subscription_id]
    
    def cancel_subscription(self, subscription_id: str) -> Subscription:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Subscription identifier
            
        Returns:
            Canceled Subscription object
            
        Raises:
            KeyError: If subscription does not exist
        """
        if subscription_id not in self.subscriptions:
            raise KeyError(f"Subscription not found: {subscription_id}")
        
        subscription = self.subscriptions[subscription_id]
        subscription.deactivate()
        
        logger.info(f"Canceled subscription {subscription_id}")
        return subscription
    
    def get_task_subscriptions(self, task_id: str) -> List[Subscription]:
        """
        Get all subscriptions for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            List of Subscription objects
        """
        if task_id not in self.task_subscriptions:
            return []
        
        subscription_ids = self.task_subscriptions[task_id]
        return [
            self.subscriptions[sub_id]
            for sub_id in subscription_ids
            if sub_id in self.subscriptions and self.subscriptions[sub_id].active
        ]
    
    async def notify(
        self, 
        task_id: str,
        event: str,
        data: Dict[str, Any],
        target_agent: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Notify subscribers of a task event.
        
        Args:
            task_id: Task identifier
            event: Event type
            data: Event data
            target_agent: Optional specific agent to notify
            trace_id: Optional workflow trace ID
            
        Returns:
            Dictionary with notification results
        """
        # Validate event
        if event not in self.VALID_EVENTS:
            raise ValueError(f"Invalid event: {event}")
        
        # Get relevant subscriptions
        subscriptions = self.get_task_subscriptions(task_id)
        if not subscriptions:
            logger.debug(f"No active subscriptions for task {task_id}")
            return {"delivered": 0, "failed": 0, "skipped": 0}
        
        # Filter subscriptions by event and target
        filtered_subscriptions = [
            sub for sub in subscriptions
            if sub.should_notify(event) and
               (target_agent is None or target_agent == sub.metadata.get("agentId"))
        ]
        
        if not filtered_subscriptions:
            logger.debug(f"No matching subscriptions for event {event} on task {task_id}")
            return {"delivered": 0, "failed": 0, "skipped": len(subscriptions)}
        
        # Create notification payload
        timestamp = self._get_timestamp()
        payload = {
            "arc": "1.0",
            "method": "task.notification",
            "requestAgent": self.agent_id,
            "taskId": task_id,
            "event": event,
            "timestamp": timestamp,
            "data": data
        }
        
        if trace_id:
            payload["traceId"] = trace_id
        
        # Deliver notifications
        results = {"delivered": 0, "failed": 0, "skipped": len(subscriptions) - len(filtered_subscriptions)}
        
        # Use asyncio.gather to deliver in parallel
        delivery_tasks = []
        for subscription in filtered_subscriptions:
            delivery_tasks.append(
                self._deliver_notification(subscription, payload)
            )
        
        if delivery_tasks:
            delivery_results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
            
            for result in delivery_results:
                if isinstance(result, Exception):
                    results["failed"] += 1
                elif result:
                    results["delivered"] += 1
                else:
                    results["failed"] += 1
        
        logger.info(
            f"Notification results for task {task_id}, event {event}: "
            f"delivered={results['delivered']}, failed={results['failed']}, "
            f"skipped={results['skipped']}"
        )
        
        return results
    
    async def _deliver_notification(
        self,
        subscription: Subscription,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Deliver notification to a subscription with retries.
        
        Args:
            subscription: Subscription to notify
            payload: Notification payload
            
        Returns:
            True if delivered, False otherwise
        """
        # Add subscription-specific fields
        delivery_payload = dict(payload)
        delivery_payload["subscriptionId"] = subscription.subscription_id
        
        # Add signature if secret is set
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"arc-sdk-python-webhooks/{subscription.subscription_id}",
            "X-ARC-Event": payload["event"],
            "X-ARC-Delivery": str(uuid.uuid4())
        }
        
        if self.webhook_secret:
            signature = self._generate_signature(json.dumps(delivery_payload))
            headers["X-ARC-Signature"] = signature
        
        # Attempt delivery with retries
        for attempt in range(self.retry_attempts):
            try:
                response = await self.http_client.post(
                    subscription.callback_url,
                    json=delivery_payload,
                    headers=headers,
                    timeout=self.webhook_timeout
                )
                
                # Check for success
                if response.status_code >= 200 and response.status_code < 300:
                    logger.debug(
                        f"Delivered notification to {subscription.subscription_id} at "
                        f"{subscription.callback_url} (status={response.status_code})"
                    )
                    return True
                
                logger.warning(
                    f"Webhook delivery failed for {subscription.subscription_id}: "
                    f"HTTP {response.status_code}"
                )
                
                # Special case: if we get a 410 Gone, deactivate subscription
                if response.status_code == 410:
                    logger.info(
                        f"Endpoint returned 410 Gone, deactivating subscription "
                        f"{subscription.subscription_id}"
                    )
                    subscription.deactivate()
                    return False
                
                # If this wasn't the last attempt, wait before retrying
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
                
            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook delivery timed out for {subscription.subscription_id} "
                    f"(attempt {attempt + 1}/{self.retry_attempts})"
                )
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.warning(
                    f"Webhook delivery error for {subscription.subscription_id}: {str(e)} "
                    f"(attempt {attempt + 1}/{self.retry_attempts})"
                )
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        logger.error(
            f"Webhook delivery failed after {self.retry_attempts} attempts "
            f"for subscription {subscription.subscription_id}"
        )
        return False
    
    def _generate_signature(self, payload: str) -> str:
        """
        Generate HMAC signature for payload.
        
        Args:
            payload: JSON payload as string
            
        Returns:
            Signature string
        """
        import hmac
        import hashlib
        import base64
        
        if not self.webhook_secret:
            return ""
        
        digest = hmac.new(
            self.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).digest()
        
        return "sha256=" + base64.b64encode(digest).decode()
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Raw JSON payload
            signature: Signature header value
            
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            return True  # No verification if no secret
        
        expected = self._generate_signature(payload)
        return hmac.compare_digest(expected, signature)
    
    def cleanup_expired_subscriptions(self, max_age_days: int = 30) -> int:
        """
        Remove expired and inactive subscriptions.
        
        Args:
            max_age_days: Maximum age of subscriptions in days
            
        Returns:
            Number of subscriptions removed
        """
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
        
        subscriptions_to_remove = []
        
        for sub_id, subscription in self.subscriptions.items():
            # Remove inactive subscriptions
            if not subscription.active:
                subscriptions_to_remove.append(sub_id)
                continue
                
            # Check subscription age
            try:
                created_time = datetime.fromisoformat(
                    subscription.created_at.replace("Z", "+00:00")
                )
                if created_time < cutoff_time:
                    subscriptions_to_remove.append(sub_id)
            except (ValueError, TypeError):
                # If we can't parse the timestamp, leave it alone
                pass
                
        # Remove subscriptions
        for sub_id in subscriptions_to_remove:
            # Clean up task index
            task_id = self.subscriptions[sub_id].task_id
            if task_id in self.task_subscriptions:
                self.task_subscriptions[task_id].discard(sub_id)
                if not self.task_subscriptions[task_id]:
                    del self.task_subscriptions[task_id]
            
            # Remove subscription
            del self.subscriptions[sub_id]
        
        logger.info(f"Cleaned up {len(subscriptions_to_remove)} expired subscriptions")
        return len(subscriptions_to_remove)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"