# agents/transcription.py
from typing import Dict
import logging
from langchain_core.messages import SystemMessage, HumanMessage
import json
from core.state import ProcessingState, CompanyInfo, Participant
from .base import BaseAgent, AgentProcessingError

logger = logging.getLogger(__name__)

class TranscriptionAgent(BaseAgent):
    """Agent responsible for analyzing transcription content."""
    
    async def process(self, state: ProcessingState) -> ProcessingState:
        """
        Process the current state and update it with transcription analysis.
        
        Args:
            state (ProcessingState): Current processing state
            
        Returns:
            ProcessingState: Updated state with analysis
        """
        try:
            # First get basic info - this must succeed
            basic_info = await self._extract_basic_info(state.transcript)
            state.summary = basic_info.get("summary", "")
            state.key_points = basic_info.get("key_points", [])
            
            # Then try to get optional company info
            try:
                company_info = await self._extract_company_info(state.transcript)
                if company_info and company_info.get("name"):  # Only set if we have valid data
                    state.company_info = CompanyInfo(**company_info)
            except Exception as e:
                logger.warning(f"Failed to extract company info: {str(e)}")
            
            # Try to get participants
            try:
                participants_info = await self._extract_participants(state.transcript)
                if participants_info:
                    state.participants = [Participant(**p) for p in participants_info]
            except Exception as e:
                logger.warning(f"Failed to extract participants: {str(e)}")
            
            return state
            
        except Exception as e:
            logger.error(f"Critical error in transcript processing: {str(e)}")
            raise AgentProcessingError(f"Transcription analysis failed: {str(e)}")

    async def _extract_basic_info(self, transcript: str) -> Dict:
        """Extract basic information from transcript."""
        try:
            prompt = SystemMessage(content="""You are an AI assistant tasked with analyzing meeting transcripts.
            Analyze the following transcript and provide a JSON response with exactly this format:
            {
                "summary": "2-3 sentence summary of key points",
                "key_points": ["key point 1", "key point 2", "key point 3"]
            }
            
            Format requirements:
            1. Response must be valid JSON
            2. Use exactly the fields shown above
            3. Summary should be business-focused and concise
            4. Include 3-5 key points
            5. Do not include any other text or explanation
            """)
            
            response = await self._call_llm([
                prompt,
                HumanMessage(content=transcript)
            ])
            
            # Clean the response - sometimes LLMs add markdown code blocks
            response = response.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {response}")
            raise AgentProcessingError("Failed to parse basic info response")
        except Exception as e:
            logger.error(f"Error in _extract_basic_info: {str(e)}")
            raise AgentProcessingError(f"Failed to extract basic info: {str(e)}")

    async def _extract_company_info(self, transcript: str) -> Dict:
        """Extract company information from transcript."""
        try:
            prompt = SystemMessage(content="""You are an AI assistant tasked with extracting company information.
            Analyze the transcript and provide a JSON response with exactly this format:
            {
                "name": "company name",
                "industry": "ai|saas|fintech|healthcare|biotech|other",
                "stage": "seed|series_a|series_b|series_c|growth",
                "revenue": number or null,
                "growth_rate": number or null,
                "location": "location or null"
            }
            
            Requirements:
            1. Response must be valid JSON
            2. Use exactly the fields shown above
            3. Use null for missing information
            4. Do not include any other text or explanation
            """)
            
            response = await self._call_llm([
                prompt,
                HumanMessage(content=transcript)
            ])
            
            # Clean and parse JSON
            response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"Error in _extract_company_info: {str(e)}")
            return None

    async def _extract_participants(self, transcript: str) -> list[Dict]:
        """Extract participant information from transcript."""
        try:
            prompt = SystemMessage(content="""You are an AI assistant tasked with extracting participant information.
            Analyze the transcript and provide a JSON response with exactly this format:
            {
                "participants": [
                    {
                        "name": "participant name",
                        "role": "role or null",
                        "company": "company name or null",
                        "key_points": ["point 1", "point 2"]
                    }
                ]
            }
            
            Requirements:
            1. Response must be valid JSON
            2. Use exactly the fields shown above
            3. Use null for missing information
            4. Do not include any other text or explanation
            """)
            
            response = await self._call_llm([
                prompt,
                HumanMessage(content=transcript)
            ])
            
            # Clean and parse JSON
            response = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(response)
            return data.get("participants", [])
            
        except Exception as e:
            logger.error(f"Error in _extract_participants: {str(e)}")
            return []
