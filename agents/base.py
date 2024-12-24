import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
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
            
            # Convert messages to a ChatPromptTemplate
            system_message = next((m for m in messages if m._message_type == "system"), None)
            human_message = next((m for m in messages if m._message_type == "human"), None)
            
            if not system_message or not human_message:
                raise ValueError("Both system and human messages are required")
            
            # Create a traceable chain
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message.content),
                ("human", "{input}")
            ])
            
            chain = LLMChain(
                llm=self.llm,
                prompt=prompt,
                verbose=False  # Disable verbose since LangSmith will handle tracing
            )
            
            # Execute with tracing and return only the chain response
            response = await chain.ainvoke({"input": human_message.content})
            return response["text"].strip()
            
        except Exception as e:
            logger.error(f"LLM call failed with error: {str(e)}", exc_info=True)
            raise AgentProcessingError(f"LLM call failed: {str(e)}")

class AgentProcessingError(Exception):
    """Raised when an agent encounters an error during processing."""
    pass
