from typing import Dict, Optional
import logging
from datetime import datetime
from core.state import ProcessingState
from core.config import AppConfig
from outputs.slack_output import SlackOutputHandler
from .transcription import TranscriptionAgent
from .decision import DecisionAgent
from .base import AgentProcessingError

logger = logging.getLogger(__name__)

class AgentWorkflow:
    """Orchestrates the flow of data through various agents."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        
        # Initialize agents
        self.transcription_agent = TranscriptionAgent(config.openai)
        self.decision_agent = DecisionAgent(config.openai, config.fund_criteria)
        
        # Initialize output handlers
        self.slack_handler = SlackOutputHandler(config.dict())
    
    async def initialize(self):
        """Initialize connections and handlers."""
        await self.slack_handler.initialize()
    
    async def process_transcript(self, transcript: str) -> ProcessingState:
        """
        Process a transcript through the entire workflow.
        
        Args:
            transcript (str): The conversation transcript to process
            
        Returns:
            ProcessingState: The final processing state
        """
        try:
            # Initialize state
            state = ProcessingState(transcript=transcript)
            start_time = datetime.now()
            
            # Run transcription analysis
            logger.info("Starting transcription analysis...")
            state = await self.transcription_agent.process(state)
            
            # Make decision
            logger.info("Making decision...")
            state = await self.decision_agent.process(state)
            
            # Calculate processing duration
            state.processing_duration = (datetime.now() - start_time).total_seconds()
            
            # Send to Slack
            logger.info("Sending results to Slack...")
            await self.slack_handler.send(state)
            
            return state
            
        except Exception as e:
            logger.error(f"Workflow processing failed: {str(e)}")
            raise
    
    async def shutdown(self):
        """Clean up resources."""
        try:
            await self.slack_handler.client.disconnect()
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")