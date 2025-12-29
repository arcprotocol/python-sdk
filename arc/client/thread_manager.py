"""
ARC Client Thread Manager

Manages thread ID mappings for CLIENT-side ARC communication.
Tracks chat_id for each agent to enable conversation continuity.
"""

import logging
from typing import Dict, Optional, List
from ..exceptions import ChatNotFoundError


logger = logging.getLogger(__name__)


class ThreadManager:
    """
    Manages thread ID mappings for CLIENT-side agent communication.
    
    Stores mapping of {agent_id: chat_id} to enable conversation reuse.
    Designed to be scoped to a user session (e.g., WebSocket handler scope).
    
    Usage:
        # In your WebSocket handler or session scope
        thread_manager = ThreadManager(arc_client)
        
        # First contact with agent - creates thread
        response = await thread_manager.send_to_agent("agent-A", message)
        
        # Subsequent contacts - reuses thread
        response = await thread_manager.send_to_agent("agent-A", message)
        
        # On disconnect
        await thread_manager.cleanup_all()
    """
    
    def __init__(self, arc_client):
        """
        Initialize thread manager.
        
        Args:
            arc_client: An ARCClient instance for making requests
        """
        self.client = arc_client
        self.mappings: Dict[str, str] = {}  # {agent_id: chat_id}
        
    def get_thread_id(self, agent_id: str) -> Optional[str]:
        """
        Get stored thread ID for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            chat_id if exists, None otherwise
        """
        return self.mappings.get(agent_id)
    
    def store_thread_id(self, agent_id: str, chat_id: str) -> None:
        """
        Store thread ID for an agent.
        
        Args:
            agent_id: Agent identifier
            chat_id: Chat/thread identifier
        """
        self.mappings[agent_id] = chat_id
        logger.debug(f"Stored thread mapping: {agent_id} -> {chat_id}")
    
    def remove_thread_id(self, agent_id: str) -> Optional[str]:
        """
        Remove thread ID mapping for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Removed chat_id if existed, None otherwise
        """
        chat_id = self.mappings.pop(agent_id, None)
        if chat_id:
            logger.debug(f"Removed thread mapping: {agent_id} -> {chat_id}")
        return chat_id
    
    def has_thread(self, agent_id: str) -> bool:
        """
        Check if thread exists for agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if thread exists, False otherwise
        """
        return agent_id in self.mappings
    
    def get_all_agents(self) -> List[str]:
        """
        Get list of all agents with active threads.
        
        Returns:
            List of agent IDs
        """
        return list(self.mappings.keys())
    
    def get_thread_count(self) -> int:
        """
        Get count of active threads.
        
        Returns:
            Number of active thread mappings
        """
        return len(self.mappings)
    
    async def send_to_agent(
        self,
        agent_id: str,
        message: Dict,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None,
        stream: bool = False
    ) -> Dict:
        """
        Send message to agent, automatically managing thread lifecycle.
        
        If thread exists, uses chat.message().
        If thread doesn't exist, uses chat.start() and stores the chat_id.
        
        Args:
            agent_id: Target agent identifier
            message: Message to send (must have 'role' and 'parts')
            trace_id: Optional workflow tracking ID
            timeout: Optional request timeout
            stream: Whether to use SSE streaming
            
        Returns:
            ARC response from agent
            
        Raises:
            ChatNotFoundError: If stored chat_id is invalid (thread expired)
        """
        chat_id = self.get_thread_id(agent_id)
        
        if chat_id:
            # Thread exists, continue conversation
            try:
                logger.debug(f"Reusing thread {chat_id} for agent {agent_id}")
                response = await self.client.chat.message(
                    target_agent=agent_id,
                    chat_id=chat_id,
                    message=message,
                    stream=stream,
                    trace_id=trace_id,
                    timeout=timeout
                )
                return response
                
            except ChatNotFoundError:
                # Thread expired on server side, remove and retry with new thread
                logger.warning(f"Thread {chat_id} not found for agent {agent_id}, creating new thread")
                self.remove_thread_id(agent_id)
                # Retry with new thread (recursive call, but only one level deep)
                return await self.send_to_agent(agent_id, message, trace_id, timeout, stream)
        
        else:
            # No thread exists, create new one
            logger.debug(f"Creating new thread for agent {agent_id}")
            response = await self.client.chat.start(
                target_agent=agent_id,
                initial_message=message,
                stream=stream,
                trace_id=trace_id,
                timeout=timeout
            )
            
            # Extract and store chat_id
            if "result" in response and "chat" in response["result"]:
                chat_id = response["result"]["chat"]["chatId"]
                self.store_thread_id(agent_id, chat_id)
                logger.info(f"Created thread {chat_id} for agent {agent_id}")
            
            return response
    
    async def end_thread(
        self,
        agent_id: str,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        End thread with specific agent.
        
        Args:
            agent_id: Agent identifier
            reason: Optional reason for ending thread
            trace_id: Optional workflow tracking ID
            
        Returns:
            Response from agent if thread existed, None otherwise
        """
        chat_id = self.get_thread_id(agent_id)
        
        if not chat_id:
            logger.debug(f"No thread to end for agent {agent_id}")
            return None
        
        try:
            logger.info(f"Ending thread {chat_id} for agent {agent_id}")
            response = await self.client.chat.end(
                target_agent=agent_id,
                chat_id=chat_id,
                reason=reason,
                trace_id=trace_id
            )
            
            # Remove mapping
            self.remove_thread_id(agent_id)
            
            return response
            
        except Exception as e:
            logger.error(f"Error ending thread for agent {agent_id}: {e}")
            # Remove mapping even on error
            self.remove_thread_id(agent_id)
            raise
    
    async def cleanup_all(self, reason: Optional[str] = None) -> Dict[str, bool]:
        """
        End all active threads and clear mappings.
        
        Typically called on session disconnect/cleanup.
        Sends chat.end() to all agents with active threads.
        
        Args:
            reason: Optional reason for cleanup (e.g., "Session ended")
            
        Returns:
            Dictionary of {agent_id: success} indicating which cleanups succeeded
        """
        if not self.mappings:
            logger.debug("No threads to clean up")
            return {}
        
        logger.info(f"Cleaning up {len(self.mappings)} active threads")
        results = {}
        
        # Get snapshot of mappings to iterate over
        agents_to_cleanup = list(self.mappings.keys())
        
        for agent_id in agents_to_cleanup:
            try:
                await self.end_thread(agent_id, reason=reason)
                results[agent_id] = True
                
            except Exception as e:
                logger.error(f"Failed to cleanup thread for agent {agent_id}: {e}")
                results[agent_id] = False
                # Still remove from mappings even if cleanup failed
                self.remove_thread_id(agent_id)
        
        logger.info(f"Cleanup complete: {sum(results.values())}/{len(results)} succeeded")
        return results
    
    def clear(self) -> None:
        """
        Clear all mappings without sending chat.end().
        
        Use with caution - agents will have orphaned threads.
        Prefer cleanup_all() for proper cleanup.
        """
        count = len(self.mappings)
        self.mappings.clear()
        logger.warning(f"Cleared {count} thread mappings without cleanup")

