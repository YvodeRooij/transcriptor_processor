import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from core.state import ProcessingState
from core.config import OpenAIConfig

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all agents in the system."""
    
    def __init__(self, openai_config: OpenAIConfig):
        self.llm = ChatOpenAI(
            api_key=openai_config.api_key,
            model=openai_config.model,
            temperature=openai_config.temperature
        )
    
    @abstractmethod
    async def process(self, state: ProcessingState) -> ProcessingState:
        """
        Process the current state and update it with new information.
        
        Args:
            state (ProcessingState): Current processing state
            
        Returns:
            ProcessingState: Updated processing state
        """
        pass
    
    async def _call_llm(self, messages: List[BaseMessage]) -> str:
        """Helper method to call LLM with error handling and tracing."""
        try:
            logger.info(f"Calling LLM with model: {self.llm.model_name}")
            
            # Validate required message types
            system_message = next((m for m in messages if m.type == "system"), None)
            human_message = next((m for m in messages if m.type == "human"), None)
            
            if not system_message or not human_message:
                raise ValueError("Both system and human messages are required")
            
            # Create a chain and execute directly
                  
            response = await self.llm.ainvoke(messages)
    
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"LLM call failed with error: {str(e)}", exc_info=True)
            raise AgentProcessingError(f"LLM call failed: {str(e)}")

class AgentProcessingError(Exception):
    """Raised when an agent encounters an error during processing."""
    pass
