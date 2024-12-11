from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from langchain_openai import ChatOpenAI
from core.state import ProcessingState
from core.config import OpenAIConfig

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
    
    async def _call_llm(self, messages: list) -> str:
        """Helper method to call LLM with error handling."""
        try:
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            raise AgentProcessingError(f"LLM call failed: {str(e)}")

class AgentProcessingError(Exception):
    """Raised when an agent encounters an error during processing."""
    pass