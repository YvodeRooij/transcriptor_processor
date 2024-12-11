from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from core.state import ProcessingState

class OutputHandler(ABC):
    """Base class for output handlers."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config

        async def initialize(self):
            """Initialize any connections or resources."""
            pass  # Base implementation is no-op
    
    @abstractmethod
    async def send(self, state: ProcessingState) -> bool:
        """
        Send the processing results to the output destination.
        
        Args:
            state (ProcessingState): The current processing state
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def update(self, state: ProcessingState) -> bool:
        """
        Update existing output with new information.
        
        Args:
            state (ProcessingState): The current processing state
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete(self, identifier: str) -> bool:
        """
        Delete output based on identifier.
        
        Args:
            identifier (str): Unique identifier for the output
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_status(self, identifier: str) -> Dict[str, Any]:
        """
        Get the status of a specific output.
        
        Args:
            identifier (str): Unique identifier for the output
            
        Returns:
            Dict[str, Any]: Status information
        """
        pass