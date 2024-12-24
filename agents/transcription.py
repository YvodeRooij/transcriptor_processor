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
            
        Raises:
            AgentProcessingError: If transcript analysis fails
        """
        if not state.transcript or not state.transcript.strip():
            raise AgentProcessingError("No transcript content provided")
            
        try:
            # First get basic info - this must succeed
            try:
                basic_info = await self._extract_basic_info(state.transcript)
                if not basic_info:
                    raise AgentProcessingError("Failed to extract basic transcript information")
                    
                state.summary = basic_info.get("summary", "")
                state.key_points = basic_info.get("key_points", [])
                
                # Validate we got meaningful content
                if not state.summary.strip() or not state.key_points:
                    raise AgentProcessingError("Failed to extract meaningful information from transcript")
                    
            except Exception as e:
                logger.error(f"Critical error extracting basic info: {str(e)}")
                raise AgentProcessingError(f"Failed to analyze transcript: {str(e)}")
            
            # Then try to get optional company info
            try:
                company_info = await self._extract_company_info(state.transcript)
                if company_info and company_info.get("name"):  # Only set if we have valid data
                    state.company_info = CompanyInfo(**company_info)
            except Exception as e:
                logger.warning(f"Failed to extract optional company info: {str(e)}")
            
            # Try to get participants
            try:
                participants_info = await self._extract_participants(state.transcript)
                if participants_info:
                    state.participants = [Participant(**p) for p in participants_info]
            except Exception as e:
                logger.warning(f"Failed to extract optional participants: {str(e)}")
            
            return state
            
        except AgentProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in transcript processing: {str(e)}")
            raise AgentProcessingError(f"Failed to process transcript: {str(e)}")

    async def _extract_basic_info(self, transcript: str) -> Dict:
        """Extract basic information from transcript."""
        prompt = SystemMessage(content="""You are a JSON-only output AI assistant that analyzes meeting transcripts.
            Your ONLY role is to output a valid JSON object with this exact structure:
            {
                "summary": "2-3 sentence summary of key points",
                "key_points": ["key point 1", "key point 2", "key point 3"]
            }
            
            Critical requirements:
            1. Output MUST be a valid JSON object - nothing else
            2. No markdown, no code blocks, no explanations
            3. No additional fields or formatting
            4. Summary should be 2-3 concise, business-focused sentences
            5. Include 3-5 key points as bullet points
            
            Example valid response:
            {"summary":"Company X presented Q4 results showing 20% growth. New product launch planned for Q2.","key_points":["Revenue grew 20% YoY","New product launching in Q2","Expanding into APAC market"]}
            """)
          
        response = await self._call_llm([
            prompt,
            HumanMessage(content=f"Analyze this transcript and provide ONLY a JSON response:\n\n{transcript}")
        ])
        
        # Enhanced JSON response cleaning and parsing
        response = response.strip()
        try:
            # Remove any markdown code blocks
            if "```" in response:
                response = response.split("```")[-2] if "```" in response.split("```")[0] else response.split("```")[1]
                response = response.replace("json", "").strip()
            
            # Find the first { and last } to extract just the JSON object
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                response = response[start:end]
            
            # Attempt to parse the cleaned JSON
            try:
                parsed = json.loads(response)
                
                # Validate required fields
                if not isinstance(parsed.get("summary"), str) or not isinstance(parsed.get("key_points"), list):
                    raise ValueError("Missing or invalid required fields")
                    
                return parsed
                
            except json.JSONDecodeError as je:
                logger.error(f"JSON parsing error: {str(je)}\nResponse: {response}")
                raise AgentProcessingError(f"Invalid JSON format: {str(je)}")
                
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {str(e)}\nRaw response: {response}")
            raise AgentProcessingError(f"Failed to extract basic info: {str(e)}")
        
    async def _extract_company_info(self, transcript: str) -> Dict:
        """Extract company information from transcript."""
        try:
            prompt = SystemMessage(content="""You are a JSON-only output AI assistant that extracts company information.
            Your ONLY role is to output a valid JSON object with this exact structure:
            {
                "name": "company name",
                "industry": "ai|saas|fintech|healthcare|biotech|other",
                "stage": "seed|series_a|series_b|series_c|growth",
                "revenue": number or null,
                "growth_rate": number or null,
                "location": "location or null"
            }
            
            Critical requirements:
            1. Output MUST be a valid JSON object - nothing else
            2. No markdown, no code blocks, no explanations
            3. Use exactly the fields shown above
            4. Use null for missing information
            
            Example valid response:
            {"name":"Acme Corp","industry":"saas","stage":"series_b","revenue":5000000,"growth_rate":150,"location":"San Francisco"}
            """)
            
            response = await self._call_llm([
                prompt,
                HumanMessage(content=f"Extract company information as JSON ONLY:\n\n{transcript}")
            ])
            
            # Enhanced JSON response cleaning and parsing
            response = response.strip()
            try:
                # Remove any markdown code blocks
                if "```" in response:
                    response = response.split("```")[-2] if "```" in response.split("```")[0] else response.split("```")[1]
                    response = response.replace("json", "").strip()
                
                # Find the first { and last } to extract just the JSON object
                start = response.find('{')
                end = response.rfind('}') + 1
                if start != -1 and end != 0:
                    response = response[start:end]
                
                # Attempt to parse the cleaned JSON
                try:
                    parsed = json.loads(response)
                    
                    # Validate required fields
                    if not isinstance(parsed.get("name"), str):
                        return None  # No valid company info found
                        
                    return parsed
                    
                except json.JSONDecodeError as je:
                    logger.error(f"JSON parsing error in company info: {str(je)}\nResponse: {response}")
                    return None
                    
            except Exception as e:
                logger.error(f"Failed to parse company info response: {str(e)}\nRaw response: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error in _extract_company_info: {str(e)}")
            return None

    async def _extract_participants(self, transcript: str) -> list[Dict]:
        """Extract participant information from transcript."""
        try:
            prompt = SystemMessage(content="""You are a JSON-only output AI assistant that extracts participant information.
            Your ONLY role is to output a valid JSON object with this exact structure:
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
            
            Critical requirements:
            1. Output MUST be a valid JSON object - nothing else
            2. No markdown, no code blocks, no explanations
            3. Use exactly the fields shown above
            4. Use null for missing information
            
            Example valid response:
            {"participants":[{"name":"John Smith","role":"CEO","company":"Acme Corp","key_points":["Discussed Q4 results","Presented growth strategy"]}]}
            """)
            
            response = await self._call_llm([
                prompt,
                HumanMessage(content=f"Extract participant information as JSON ONLY:\n\n{transcript}")
            ])
            
            # Enhanced JSON response cleaning and parsing
            response = response.strip()
            try:
                # Remove any markdown code blocks
                if "```" in response:
                    response = response.split("```")[-2] if "```" in response.split("```")[0] else response.split("```")[1]
                    response = response.replace("json", "").strip()
                
                # Find the first { and last } to extract just the JSON object
                start = response.find('{')
                end = response.rfind('}') + 1
                if start != -1 and end != 0:
                    response = response[start:end]
                
                # Attempt to parse the cleaned JSON
                try:
                    parsed = json.loads(response)
                    
                    # Validate required fields
                    participants = parsed.get("participants", [])
                    if not isinstance(participants, list):
                        return []
                        
                    # Validate each participant has required fields
                    valid_participants = []
                    for p in participants:
                        if isinstance(p, dict) and isinstance(p.get("name"), str):
                            valid_participants.append(p)
                            
                    return valid_participants
                    
                except json.JSONDecodeError as je:
                    logger.error(f"JSON parsing error in participants: {str(je)}\nResponse: {response}")
                    return []
                    
            except Exception as e:
                logger.error(f"Failed to parse participants response: {str(e)}\nRaw response: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Error in _extract_participants: {str(e)}")
            return []
