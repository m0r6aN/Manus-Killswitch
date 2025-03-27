"""
Enhanced Reconciliation Protocol
-------------------------------
Advanced implementation of the reconciliation protocol between AI agents
with improved critique generation and deeper iteration on contested responses.
"""

import json
import logging
import re
import asyncio
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reconciliation")

@dataclass
class CritiquePoint:
    """A specific critique point from one agent about another agent's response."""
    from_agent: str
    to_agent: str
    point_type: str  # "strength" or "weakness"
    description: str
    confidence: float = 0.8
    impact_level: str = "medium"  # low, medium, high
    
    def to_dict(self) -> Dict:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "point_type": self.point_type,
            "description": self.description,
            "confidence": self.confidence,
            "impact_level": self.impact_level
        }

@dataclass
class AgentCritique:
    """Complete critique from one agent about other agents' responses."""
    agent_id: str
    target_agents: List[str]
    strengths: List[CritiquePoint]
    weaknesses: List[CritiquePoint]
    alternative_approach: Optional[str] = None
    synthesis_recommendation: Optional[str] = None
    round_num: int = 1
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "target_agents": self.target_agents,
            "strengths": [s.to_dict() for s in self.strengths],
            "weaknesses": [w.to_dict() for w in self.weaknesses],
            "alternative_approach": self.alternative_approach,
            "synthesis_recommendation": self.synthesis_recommendation,
            "round_num": self.round_num,
            "timestamp": self.timestamp or datetime.now().isoformat()
        }

class EnhancedReconciliationProtocol:
    """
    Enhanced protocol for structured reconciliation between AI agents
    with improved critique generation and debate depth.
    """
    
    def __init__(self, confidence_scorer=None):
        """
        Initialize the reconciliation protocol.
        
        Args:
            confidence_scorer: Optional confidence scorer to use
        """
        self.confidence_scorer = confidence_scorer
        self.logger = logging.getLogger("reconciliation")
        
        # Track critique history to prevent repetition
        self.critique_history = {}
    
    async def generate_critique_prompt(self, 
                                 agent_id: str, 
                                 agent_response: Dict, 
                                 other_responses: List[Dict],
                                 round_num: int,
                                 previous_critiques: Optional[List[Dict]] = None,
                                 query: Optional[str] = None) -> str:
        """
        Generate an enhanced prompt for an agent to critique other agents' responses.
        
        Args:
            agent_id: The ID of the agent to generate the critique for
            agent_response: The agent's own response
            other_responses: Responses from other agents
            round_num: The current reconciliation round number
            previous_critiques: Previous critiques from earlier rounds
            query: The original query that started the debate
            
        Returns:
            A detailed prompt for the agent to critique other responses
        """
        prompt_parts = [
            f"# AI Council Reconciliation Protocol - Round {round_num}\n\n",
        ]
        
        # Add the original query if available
        if query:
            prompt_parts.append(f"## Original Query\n\n{query}\n\n")
        
        # Add context about the reconciliation process
        prompt_parts.append(
            "You are participating in a multi-agent AI Council deliberation process. "
            "Your task is to carefully evaluate other agents' responses, compare them with your own, "
            "identify strengths and weaknesses, and work toward the most accurate and useful consensus.\n\n"
        )
        
        # Add specific instructions for this round
        if round_num == 1:
            prompt_parts.append(
                "## First Round Instructions\n\n"
                "In this first round, focus on a thorough initial assessment:\n\n"
                "1. Identify specific strengths in each agent's response\n"
                "2. Identify specific weaknesses or gaps in each agent's response\n"
                "3. Consider how these different perspectives might be integrated\n"
                "4. Maintain intellectual humility - acknowledge strengths in other approaches\n\n"
            )
        elif round_num == 2:
            prompt_parts.append(
                "## Second Round Instructions\n\n"
                "Now that initial critiques have been shared:\n\n"
                "1. Address the specific critiques made about your previous response\n"
                "2. Identify areas where your position has evolved based on others' input\n"
                "3. Focus on remaining disagreements and attempt to resolve them\n"
                "4. Suggest specific ways to synthesize the best elements from all perspectives\n\n"
            )
        else:
            prompt_parts.append(
                f"## Final Reconciliation Round {round_num}\n\n"
                "This is a final reconciliation round:\n\n"
                "1. Make your strongest case for consensus points everyone should agree on\n"
                "2. For any points where consensus isn't possible, clearly articulate why\n"
                "3. Present your final synthesized perspective, incorporating valuable elements from all agents\n"
                "4. Rate your confidence in different components of your response\n\n"
            )
        
        # Add the agent's own response
        prompt_parts.append(f"## Your Previous Response\n\n{agent_response.get('content', '')}\n\n")
        prompt_parts.append(f"### Your Previous Reasoning\n\n{agent_response.get('reasoning', 'No reasoning provided.')}\n\n")
        
        # Add other agents' responses
        prompt_parts.append("## Other Agents' Responses\n\n")
        for resp in other_responses:
            other_agent = resp.get('agent_id', 'Unknown')
            prompt_parts.append(f"### {other_agent}'s Response\n\n{resp.get('content', '')}\n\n")
            prompt_parts.append(f"#### {other_agent}'s Reasoning\n\n{resp.get('reasoning', 'No reasoning provided.')}\n\n")
        
        # If we have previous critiques, include them
        if previous_critiques and round_num > 1:
            prompt_parts.append("## Previous Round Critiques\n\n")
            
            # First, show critiques directed at this agent
            critiques_of_this_agent = [c for c in previous_critiques 
                                     if agent_id in c.get('target_agents', [])]
            
            if critiques_of_this_agent:
                prompt_parts.append("### Critiques of Your Response\n\n")
                for critique in critiques_of_this_agent:
                    critic_id = critique.get('agent_id', 'Unknown')
                    prompt_parts.append(f"**From {critic_id}:**\n\n")
                    
                    # Add strengths
                    strengths = [s for s in critique.get('strengths', []) 
                               if s.get('to_agent') == agent_id]
                    if strengths:
                        prompt_parts.append("*Strengths identified:*\n\n")
                        for s in strengths:
                            prompt_parts.append(f"- {s.get('description', '')}\n")
                        prompt_parts.append("\n")
                    
                    # Add weaknesses
                    weaknesses = [w for w in critique.get('weaknesses', []) 
                                if w.get('to_agent') == agent_id]
                    if weaknesses:
                        prompt_parts.append("*Areas for improvement:*\n\n")
                        for w in weaknesses:
                            prompt_parts.append(f"- {w.get('description', '')}\n")
                        prompt_parts.append("\n")
            
            # Then, show critiques from this agent
            critiques_from_this_agent = [c for c in previous_critiques 
                                       if c.get('agent_id') == agent_id]
            
            if critiques_from_this_agent and len(critiques_from_this_agent) > 0:
                prompt_parts.append("### Your Previous Critiques\n\n")
                for critique in critiques_from_this_agent:
                    for target in critique.get('target_agents', []):
                        prompt_parts.append(f"**Your critique of {target}:**\n\n")
                        
                        # Add strengths
                        strengths = [s for s in critique.get('strengths', []) 
                                   if s.get('to_agent') == target]
                        if strengths:
                            prompt_parts.append("*Strengths you identified:*\n\n")
                            for s in strengths:
                                prompt_parts.append(f"- {s.get('description', '')}\n")
                            prompt_parts.append("\n")
                        
                        # Add weaknesses
                        weaknesses = [w for w in critique.get('weaknesses', []) 
                                    if w.get('to_agent') == target]
                        if weaknesses:
                            prompt_parts.append("*Areas for improvement you identified:*\n\n")
                            for w in weaknesses:
                                prompt_parts.append(f"- {w.get('description', '')}\n")
                            prompt_parts.append("\n")
        
        # Add instructions for the response format
        prompt_parts.append(
            "## Response Format\n\n"
            "Please structure your response in the following format:\n\n"
            "1. **Critique of Other Agents**\n"
            "   - Strengths of each agent's response\n"
            "   - Weaknesses or gaps in each agent's response\n\n"
            "2. **Integration & Synthesis**\n"
            "   - How different perspectives can be combined\n"
            "   - Your recommended synthesized approach\n\n"
            "3. **Updated Response**\n"
            "   - Your revised response incorporating valuable insights\n"
            "   - Clear reasoning for your updates\n\n"
            "4. **Confidence Assessment**\n"
            "   - Rate your confidence in your response (0-100%)\n"
            "   - Identify which parts you're most/least confident about\n\n"
        )
        
        return "".join(prompt_parts)
    
    async def parse_critique_response(self, 
                                agent_id: str,
                                raw_response: str,
                                target_agents: List[str],
                                round_num: int) -> AgentCritique:
        """
        Parse a raw critique response from an agent.
        In a real implementation, this would extract structured data from the agent's response.
        For this demo, we'll simulate parsing.
        
        Args:
            agent_id: The ID of the agent that provided the critique
            raw_response: The raw response text from the agent
            target_agents: List of agent IDs that were critiqued
            round_num: The current reconciliation round
            
        Returns:
            A structured AgentCritique object
        """
        # This would normally use NLP to extract structured critiques
        # For demo purposes, we'll simulate the extraction
        
        # Track strengths and weaknesses
        strengths = []
        weaknesses = []
        alternative_approach = None
        synthesis = None
        
        # Simplified extraction using regex patterns
        # In real implementation, use more sophisticated NLP
        
        # Extract strengths (look for sections or bullet points about strengths)
        strength_pattern = r"(?:strength|positive|good|effective|useful).*?(?:\n|$)"
        strength_matches = re.finditer(strength_pattern, raw_response, re.IGNORECASE)
        
        for i, match in enumerate(strength_matches):
            # Distribute strengths among target agents
            if target_agents:
                target_idx = i % len(target_agents)
                target = target_agents[target_idx]
                
                strengths.append(CritiquePoint(
                    from_agent=agent_id,
                    to_agent=target,
                    point_type="strength",
                    description=match.group(0).strip(),
                    confidence=0.8,
                    impact_level="medium"
                ))
        
        # Extract weaknesses
        weakness_pattern = r"(?:weakness|negative|issue|problem|concern|improve).*?(?:\n|$)"
        weakness_matches = re.finditer(weakness_pattern, raw_response, re.IGNORECASE)
        
        for i, match in enumerate(weakness_matches):
            # Distribute weaknesses among target agents
            if target_agents:
                target_idx = i % len(target_agents)
                target = target_agents[target_idx]
                
                weaknesses.append(CritiquePoint(
                    from_agent=agent_id,
                    to_agent=target,
                    point_type="weakness",
                    description=match.group(0).strip(),
                    confidence=0.7,
                    impact_level="medium"
                ))
        
        # Extract alternative approach
        alt_pattern = r"(?:alternative|different approach|instead|recommend).*?(?:\n\n|$)"
        alt_matches = re.search(alt_pattern, raw_response, re.IGNORECASE)
        if alt_matches:
            alternative_approach = alt_matches.group(0).strip()
        
        # Extract synthesis recommendation
        synth_pattern = r"(?:synthesis|combine|integrate|synthesize|consensus).*?(?:\n\n|$)"
        synth_matches = re.search(synth_pattern, raw_response, re.IGNORECASE)
        if synth_matches:
            synthesis = synth_matches.group(0).strip()
        
        # If we didn't find much, create some simulated critique points
        if len(strengths) < 2 and target_agents:
            for target in target_agents:
                strengths.append(CritiquePoint(
                    from_agent=agent_id,
                    to_agent=target,
                    point_type="strength",
                    description=f"Simulated strength point for {target}",
                    confidence=0.8,
                    impact_level="medium"
                ))
        
        if len(weaknesses) < 2 and target_agents:
            for target in target_agents:
                weaknesses.append(CritiquePoint(
                    from_agent=agent_id,
                    to_agent=target,
                    point_type="weakness",
                    description=f"Simulated weakness point for {target}",
                    confidence=0.7,
                    impact_level="medium"
                ))
        
        # Create the agent critique
        critique = AgentCritique(
            agent_id=agent_id,
            target_agents=target_agents,
            strengths=strengths,
            weaknesses=weaknesses,
            alternative_approach=alternative_approach,
            synthesis_recommendation=synthesis,
            round_num=round_num,
            timestamp=datetime.now().isoformat()
        )
        
        return critique
    
    async def generate_consolidated_report(self, 
                                     all_critiques: List[AgentCritique],
                                     final_responses: List[Dict]) -> Dict:
        """
        Generate a consolidated report of the reconciliation process.
        
        Args:
            all_critiques: All critiques from all rounds
            final_responses: The final responses from all agents
            
        Returns:
            A consolidated report
        """
        # Group critiques by round
        critiques_by_round = {}
        for critique in all_critiques:
            round_num = critique.round_num
            if round_num not in critiques_by_round:
                critiques_by_round[round_num] = []
            critiques_by_round[round_num].append(critique)
        
        # Initialize the report
        report = {
            "total_rounds": max(critiques_by_round.keys()) if critiques_by_round else 0,
            "total_critiques": len(all_critiques),
            "round_summaries": [],
            "key_consensus_points": [],
            "key_disagreement_points": [],
            "agent_journey": {},
            "final_perspectives": {}
        }
        
        # Generate round summaries
        for round_num in sorted(critiques_by_round.keys()):
            round_critiques = critiques_by_round[round_num]
            
            # Count critiques by type
            total_strengths = sum(len(c.strengths) for c in round_critiques)
            total_weaknesses = sum(len(c.weaknesses) for c in round_critiques)
            
            # Calculate average strengths and weaknesses per agent
            num_agents = len({c.agent_id for c in round_critiques})
            avg_strengths = total_strengths / max(1, num_agents)
            avg_weaknesses = total_weaknesses / max(1, num_agents)
            
            round_summary = {
                "round": round_num,
                "critiques_count": len(round_critiques),
                "total_strengths_identified": total_strengths,
                "total_weaknesses_identified": total_weaknesses,
                "avg_strengths_per_agent": avg_strengths,
                "avg_weaknesses_per_agent": avg_weaknesses,
                "notable_patterns": []
            }
            
            # Identify notable patterns (simplified for demo)
            if avg_strengths > avg_weaknesses * 2:
                round_summary["notable_patterns"].append(
                    "Agents were significantly more positive than critical"
                )
            elif avg_weaknesses > avg_strengths * 2:
                round_summary["notable_patterns"].append(
                    "Agents were significantly more critical than positive"
                )
            
            if round_num > 1 and round_num in critiques_by_round:
                prev_round = critiques_by_round[round_num - 1]
                prev_weaknesses = sum(len(c.weaknesses) for c in prev_round)
                
                if total_weaknesses < prev_weaknesses * 0.7:
                    round_summary["notable_patterns"].append(
                        "Significant reduction in criticisms compared to previous round"
                    )
            
            report["round_summaries"].append(round_summary)
        
        # Track agent journey through the debate
        for critique in all_critiques:
            agent_id = critique.agent_id
            if agent_id not in report["agent_journey"]:
                report["agent_journey"][agent_id] = {
                    "critiques_made": [],
                    "critiques_received": []
                }
            
            # Add critique made
            report["agent_journey"][agent_id]["critiques_made"].append({
                "round": critique.round_num,
                "target_agents": critique.target_agents,
                "strengths_count": len(critique.strengths),
                "weaknesses_count": len(critique.weaknesses)
            })
        
        # Add critiques received
        for critique in all_critiques:
            for strength in critique.strengths:
                target = strength.to_agent
                if target in report["agent_journey"]:
                    report["agent_journey"][target]["critiques_received"].append({
                        "round": critique.round_num,
                        "from_agent": critique.agent_id,
                        "type": "strength",
                        "description": strength.description
                    })
            
            for weakness in critique.weaknesses:
                target = weakness.to_agent
                if target in report["agent_journey"]:
                    report["agent_journey"][target]["critiques_received"].append({
                        "round": critique.round_num,
                        "from_agent": critique.agent_id,
                        "type": "weakness",
                        "description": weakness.description
                    })
        
        # Add final perspectives
        for resp in final_responses:
            agent_id = resp.get("agent_id", "unknown")
            content = resp.get("content", "")
            confidence = resp.get("confidence", 0.0)
            
            # Extract a summary (first 200 chars for demo)
            summary = content[:200] + "..." if len(content) > 200 else content
            
            report["final_perspectives"][agent_id] = {
                "summary": summary,
                "confidence": confidence,
                "final_position": self._categorize_position(resp, all_critiques)
            }
        
        # Generate key consensus and disagreement points
        # This would normally use NLP to extract common themes
        # For demo, use simple string matching on critiques
        
        # Extract common themes from alternative approaches and syntheses
        themes = []
        for critique in all_critiques:
            if critique.alternative_approach:
                themes.append(critique.alternative_approach)
            if critique.synthesis_recommendation:
                themes.append(critique.synthesis_recommendation)
        
        # Simple extraction of common phrases (3+ words)
        common_phrases = self._extract_common_phrases(themes, min_phrase_len=3)
        
        # Add top phrases as consensus points
        report["key_consensus_points"] = common_phrases[:5]  # Top 5
        
        # Extract disagreement points from weaknesses
        all_weaknesses = []
        for critique in all_critiques:
            for weakness in critique.weaknesses:
                all_weaknesses.append(weakness.description)
        
        # Extract common criticism themes
        disagreement_themes = self._extract_common_phrases(all_weaknesses, min_phrase_len=2)
        report["key_disagreement_points"] = disagreement_themes[:5]  # Top 5
        
        return report
    
    def _extract_common_phrases(self, texts: List[str], min_phrase_len: int = 3) -> List[str]:
        """
        Extract common phrases from a list of texts.
        Very simplified implementation for demo purposes.
        
        Args:
            texts: List of text strings
            min_phrase_len: Minimum number of words in a phrase
            
        Returns:
            List of common phrases
        """
        if not texts:
            return []
        
        # Just a simple implementation for demo
        # In a real system, use proper NLP techniques
        common_phrases = set()
        
        # Join all texts and split into sentences
        all_text = " ".join(texts)
        sentences = re.split(r'[.!?]', all_text)
        
        for sentence in sentences:
            words = sentence.split()
            if len(words) >= min_phrase_len:
                # Extract phrases of min_phrase_len words
                for i in range(len(words) - min_phrase_len + 1):
                    phrase = " ".join(words[i:i+min_phrase_len])
                    # Filter out phrases with stopwords only
                    if len(phrase) > 10 and not re.match(r'^(the|and|or|but|of|in|on|at|to|for|with|by|about)\s+', phrase, re.IGNORECASE):
                        common_phrases.add(phrase)
        
        # Sort by frequency (simplified)
        phrase_counts = {}
        for phrase in common_phrases:
            count = sum(1 for text in texts if phrase.lower() in text.lower())
            phrase_counts[phrase] = count
        
        sorted_phrases = sorted(phrase_counts.keys(), key=lambda p: phrase_counts[p], reverse=True)
        return sorted_phrases
    
    def _categorize_position(self, final_response: Dict, all_critiques: List[AgentCritique]) -> str:
        """
        Categorize an agent's final position relative to the debate.
        
        Args:
            final_response: The agent's final response
            all_critiques: All critiques from the debate
            
        Returns:
            A category label for the agent's position
        """
        agent_id = final_response.get("agent_id", "unknown")
        confidence = final_response.get("confidence", 0.0)
        
        # Count how many critiques this agent made and received
        critiques_made = sum(1 for c in all_critiques if c.agent_id == agent_id)
        
        critiques_received = 0
        for critique in all_critiques:
            for strength in critique.strengths:
                if strength.to_agent == agent_id:
                    critiques_received += 1
            for weakness in critique.weaknesses:
                if weakness.to_agent == agent_id:
                    critiques_received += 1
        
        # Determine the agent's role in the debate
        if confidence > 0.85 and critiques_made > critiques_received:
            return "leader"
        elif critiques_made > critiques_received * 2:
            return "critic"
        elif critiques_received > critiques_made * 2:
            return "receiver"
        elif confidence < 0.6:
            return "uncertain"
        else:
            return "contributor"
    
    async def generate_enhanced_prompts(self,
                                  agent_ids: List[str],
                                  query: str,
                                  responses: List[Dict],
                                  round_num: int,
                                  previous_critiques: Optional[List[AgentCritique]] = None) -> Dict[str, str]:
        """
        Generate enhanced prompts for all agents in a reconciliation round.
        
        Args:
            agent_ids: List of agent IDs to generate prompts for
            query: The original query
            responses: Current responses from all agents
            round_num: The current reconciliation round
            previous_critiques: Previous critiques from earlier rounds
            
        Returns:
            Dictionary mapping agent IDs to their prompts
        """
        prompts = {}
        
        for agent_id in agent_ids:
            # Get this agent's response
            agent_response = next((r for r in responses if r.get("agent_id") == agent_id), {})
            
            # Get other agents' responses
            other_responses = [r for r in responses if r.get("agent_id") != agent_id]
            
            # Generate the prompt
            prompt = await self.generate_critique_prompt(
                agent_id=agent_id,
                agent_response=agent_response,
                other_responses=other_responses,
                round_num=round_num,
                previous_critiques=[c.to_dict() for c in (previous_critiques or [])],
                query=query
            )
            
            prompts[agent_id] = prompt
        
        return prompts
    
    async def process_critique_responses(self,
                                   raw_responses: Dict[str, str],
                                   target_map: Dict[str, List[str]],
                                   round_num: int) -> List[AgentCritique]:
        """
        Process raw critique responses from all agents.
        
        Args:
            raw_responses: Dictionary mapping agent IDs to their raw responses
            target_map: Dictionary mapping agent IDs to their critique targets
            round_num: The current reconciliation round
            
        Returns:
            List of structured AgentCritique objects
        """
        critiques = []
        
        for agent_id, raw_response in raw_responses.items():
            target_agents = target_map.get(agent_id, [])
            
            # Parse the critique
            critique = await self.parse_critique_response(
                agent_id=agent_id,
                raw_response=raw_response,
                target_agents=target_agents,
                round_num=round_num
            )
            
            critiques.append(critique)
        
        return critiques
    
    async def run_complete_reconciliation(self,
                                    initial_responses: List[Dict],
                                    query: str,
                                    max_rounds: int = 3,
                                    redis_client = None) -> Tuple[List[Dict], Dict]:
        """
        Run a complete reconciliation process from start to finish.
        
        Args:
            initial_responses: Initial responses from all agents
            query: The original query
            max_rounds: Maximum number of reconciliation rounds
            redis_client: Optional Redis client for event publishing
            
        Returns:
            Tuple of (final_responses, reconciliation_report)
        """
        agent_ids = [r.get("agent_id") for r in initial_responses]
        current_responses = initial_responses
        all_critiques = []
        
        # Run the reconciliation rounds
        for round_num in range(1, max_rounds + 1):
            self.logger.info(f"Starting reconciliation round {round_num}")
            
            if redis_client:
                # Publish round start event
                await redis_client.publish(
                    "ai_council:reconciliation", 
                    json.dumps({
                        "event": "round_started",
                        "round": round_num,
                        "timestamp": datetime.now().isoformat(),
                        "agent_count": len(agent_ids)
                    })
                )
            
            # Create target map (each agent critiques all others)
            target_map = {}
            for agent_id in agent_ids:
                target_map[agent_id] = [aid for aid in agent_ids if aid != agent_id]
            
            # Generate enhanced prompts for all agents
            prompts = await self.generate_enhanced_prompts(
                agent_ids=agent_ids,
                query=query,
                responses=current_responses,
                round_num=round_num,
                previous_critiques=all_critiques if round_num > 1 else None
            )
            
            # In a real implementation, send these prompts to the actual agents
            # For demo, we'll simulate the responses
            raw_responses = {}
            for agent_id, prompt in prompts.items():
                # In real impl, call the agent API with the prompt
                # For demo, generate a simulated response
                raw_responses[agent_id] = f"Simulated critique response from {agent_id} in round {round_num}"
                
                if redis_client:
                    # Publish agent prompt event
                    await redis_client.publish(
                        "ai_council:reconciliation", 
                        json.dumps({
                            "event": "agent_prompted",
                            "round": round_num,
                            "agent_id": agent_id,
                            "timestamp": datetime.now().isoformat(),
                            "prompt_length": len(prompt)
                        })
                    )
            
            # Process the critique responses
            round_critiques = await self.process_critique_responses(
                raw_responses=raw_responses,
                target_map=target_map,
                round_num=round_num
            )
            
            # Add to all critiques
            all_critiques.extend(round_critiques)
            
            if redis_client:
                # Publish critiques received event
                await redis_client.publish(
                    "ai_council:reconciliation", 
                    json.dumps({
                        "event": "critiques_received",
                        "round": round_num,
                        "critique_count": len(round_critiques),
                        "timestamp": datetime.now().isoformat()
                    })
                )
            
            # In a real implementation, agents would now update their responses
            # based on the critiques. For demo, simulate updated responses.
            updated_responses = []
            for i, resp in enumerate(current_responses):
                agent_id = resp.get("agent_id", f"agent_{i}")
                
                # Simulate content changes based on round
                original_content = resp.get("content", "")
                confidence = resp.get("confidence", 0.7)
                
                # Simulate evolution of response with each round
                if round_num == 1:
                    # First round: minor adjustments, slight confidence decrease
                    updated_content = original_content + f"\n\nAfter round {round_num}, I've considered feedback from other agents."
                    updated_confidence = confidence * 0.95  # Slight decrease as they consider alternatives
                elif round_num == max_rounds - 1:
                    # Penultimate round: more significant adjustments, confidence may increase
                    updated_content = f"Based on multiple rounds of feedback, my revised view is: {original_content}"
                    updated_confidence = confidence * 1.05  # Slight increase as they refine their view
                else:
                    # Final round: synthesis and consolidation
                    updated_content = f"Final synthesis after {round_num} rounds of debate: {original_content}"
                    updated_confidence = confidence * 1.1  # Increased confidence in final position
                
                updated_responses.append({
                    "agent_id": agent_id,
                    "content": updated_content,
                    "confidence": min(0.95, updated_confidence),  # Cap at 0.95
                    "reasoning": f"After {round_num} rounds of critique and revision, this is my updated perspective.",
                    "round": round_num
                })
            
            current_responses = updated_responses
            
            if redis_client:
                # Publish round completed event
                await redis_client.publish(
                    "ai_council:reconciliation", 
                    json.dumps({
                        "event": "round_completed",
                        "round": round_num,
                        "timestamp": datetime.now().isoformat(),
                        "response_count": len(current_responses)
                    })
                )
        
        # Generate final reconciliation report
        report = await self.generate_consolidated_report(
            all_critiques=all_critiques,
            final_responses=current_responses
        )
        
        if redis_client:
            # Publish reconciliation completed event
            await redis_client.publish(
                "ai_council:reconciliation", 
                json.dumps({
                    "event": "reconciliation_completed",
                    "total_rounds": max_rounds,
                    "timestamp": datetime.now().isoformat(),
                    "consensus_points": len(report["key_consensus_points"]),
                    "disagreement_points": len(report["key_disagreement_points"])
                })
            )
        
        return current_responses, report


# Example usage:
"""
# Initialize the protocol
reconciliation = EnhancedReconciliationProtocol()

# Example initial responses
initial_responses = [
    {
        "agent_id": "Claude",
        "content": "I believe the ethical approach is to prioritize...",
        "confidence": 0.85,
        "reasoning": "Based on utilitarian principles..."
    },
    {
        "agent_id": "GPT",
        "content": "The solution should balance both perspectives by...",
        "confidence": 0.78,
        "reasoning": "Drawing from multiple ethical frameworks..."
    },
    {
        "agent_id": "Grok",
        "content": "The most practical approach is to...",
        "confidence": 0.82,
        "reasoning": "Focusing on pragmatic outcomes..."
    }
]

# Run the complete reconciliation process
final_responses, report = await reconciliation.run_complete_reconciliation(
    initial_responses=initial_responses,
    query="What is the most ethical solution to the trolley problem?",
    max_rounds=3
)

print(f"Final responses: {len(final_responses)}")
print(f"Consensus points: {len(report['key_consensus_points'])}")
print(f"Disagreement points: {len(report['key_disagreement_points'])}")
"""