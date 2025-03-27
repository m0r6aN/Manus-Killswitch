"""
Enhanced Decision Arbitration Module
-----------------------------------
Upgraded version with refined confidence scoring and improved reconciliation logic
for more dynamic AI Council decision-making.
"""

import json
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from enum import Enum, auto
from dataclasses import dataclass, field
import asyncio
import re
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("decision_arbitration")

class ResponseStatus(Enum):
    CONSENSUS = auto()
    STRONG_CONFIDENCE = auto() 
    DEBATING = auto()
    RECONCILED = auto()
    MAJORITY_WITH_DISSENT = auto()
    DEADLOCKED = auto()
    PARTIAL_CONSENSUS = auto()  # New status for partial agreement

@dataclass
class AgentResponse:
    agent_id: str
    content: str
    confidence: float
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    critique_of: Optional[List[str]] = None  # List of agent IDs this response critiques
    strengths: Optional[List[str]] = None    # Key strengths identified
    weaknesses: Optional[List[str]] = None   # Key weaknesses identified
    round_num: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "content": self.content,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "critique_of": self.critique_of,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "round_num": self.round_num
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentResponse':
        return cls(
            agent_id=data["agent_id"],
            content=data["content"],
            confidence=data["confidence"],
            reasoning=data["reasoning"],
            metadata=data.get("metadata", {}),
            critique_of=data.get("critique_of"),
            strengths=data.get("strengths"),
            weaknesses=data.get("weaknesses"),
            round_num=data.get("round_num", 0)
        )

@dataclass
class DebateMetrics:
    response_variations: int = 0           # How many distinct responses exist
    average_confidence: float = 0.0        # Average confidence across agents
    confidence_spread: float = 0.0         # Difference between highest and lowest
    cross_references: int = 0              # How many times agents reference each other
    critique_depth: float = 0.0            # Depth of critiques (1-10 scale)
    convergence_rate: float = 0.0          # How quickly agents converge (0-1)
    disagreement_level: float = 0.0        # Level of disagreement (0-1)
    
    def to_dict(self) -> Dict:
        return {
            "response_variations": self.response_variations,
            "average_confidence": self.average_confidence,
            "confidence_spread": self.confidence_spread,
            "cross_references": self.cross_references,
            "critique_depth": self.critique_depth,
            "convergence_rate": self.convergence_rate,
            "disagreement_level": self.disagreement_level
        }

@dataclass
class ArbitrationResult:
    status: ResponseStatus
    content: str
    confidence: float
    contributing_agents: List[str]
    debate_log: List[Dict]
    debate_metrics: DebateMetrics = field(default_factory=DebateMetrics)
    dissenting_view: Optional[str] = None
    dissenting_agents: Optional[List[str]] = None
    key_points_consensus: Optional[List[str]] = None
    key_points_dissent: Optional[List[str]] = None
    reconciliation_rounds: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.name,
            "content": self.content,
            "confidence": self.confidence,
            "contributing_agents": self.contributing_agents,
            "debate_log": self.debate_log,
            "debate_metrics": self.debate_metrics.to_dict(),
            "dissenting_view": self.dissenting_view,
            "dissenting_agents": self.dissenting_agents,
            "key_points_consensus": self.key_points_consensus,
            "key_points_dissent": self.key_points_dissent,
            "reconciliation_rounds": self.reconciliation_rounds
        }


class EnhancedDecisionArbitrator:
    """Enhanced decision arbitration with improved confidence scoring and reconciliation."""
    
    def __init__(self, 
                 confidence_threshold: float = 0.25,  # Lowered for more debates
                 consensus_threshold: float = 0.15,   # Increased for stricter consensus req
                 max_debate_rounds: int = 4,          # Increased max rounds
                 min_debate_rounds: int = 2,          # Added minimum rounds
                 topic_extraction_enabled: bool = True):
        self.confidence_threshold = confidence_threshold
        self.consensus_threshold = consensus_threshold
        self.max_debate_rounds = max_debate_rounds
        self.min_debate_rounds = min_debate_rounds
        self.topic_extraction_enabled = topic_extraction_enabled
        self.debate_log = []
        
    async def arbitrate(self, 
                  responses: List[AgentResponse], 
                  redis_client = None,
                  query: Optional[str] = None) -> ArbitrationResult:
        """
        Main arbitration function with improved decision logic.
        """
        logger.info(f"Starting enhanced arbitration with {len(responses)} agent responses")
        self.debate_log = []
        start_time = datetime.now()
        
        # Log initial responses
        for resp in responses:
            resp.round_num = 0  # Ensure initial round is set
            self.debate_log.append({
                "round": 0,
                "agent": resp.agent_id,
                "content": resp.content,
                "confidence": resp.confidence,
                "reasoning": resp.reasoning,
                "timestamp": datetime.now().isoformat()
            })
        
        # Initialize debate metrics
        debate_metrics = self._calculate_debate_metrics(responses)
        
        # Force minimum debate rounds - don't check for consensus initially
        current_responses = responses
        force_debate = self.min_debate_rounds > 0
        
        # Run at least min_debate_rounds of reconciliation
        reconciliation_rounds = 0
        
        for round_num in range(1, self.max_debate_rounds + 1):
            # Skip consensus check if we haven't hit minimum rounds
            if not force_debate:
                # Check for consensus
                if self._has_consensus(current_responses):
                    logger.info(f"Consensus detected in round {round_num}")
                    result = self._build_consensus_result(current_responses, debate_metrics)
                    result.reconciliation_rounds = reconciliation_rounds
                    return result
                
                # Check for strong confidence differential
                highest_conf_response = max(current_responses, key=lambda r: r.confidence)
                if round_num > 1 and self._has_strong_confidence(current_responses, highest_conf_response):
                    logger.info(f"Strong confidence differential detected in round {round_num}")
                    result = self._build_strong_confidence_result(current_responses, highest_conf_response, debate_metrics)
                    result.reconciliation_rounds = reconciliation_rounds
                    return result
            
            # Run a reconciliation round
            logger.info(f"Starting reconciliation round {round_num}")
            reconciliation_rounds += 1
            
            # Publish round start event
            if redis_client:
                await redis_client.publish(
                    "ai_council:debate", 
                    json.dumps({
                        "round": round_num,
                        "status": "in_progress",
                        "responses": [r.to_dict() for r in current_responses],
                        "timestamp": datetime.now().isoformat()
                    })
                )
            
            # In a real implementation, this would call actual agent APIs with critique prompts
            # For this demo, we'll simulate the reconciliation
            new_responses = await self._run_reconciliation_round(
                current_responses, round_num, query, redis_client
            )
            
            # Update the debate log
            for resp in new_responses:
                self.debate_log.append({
                    "round": round_num,
                    "agent": resp.agent_id,
                    "content": resp.content,
                    "confidence": resp.confidence,
                    "reasoning": resp.reasoning,
                    "critique_of": resp.critique_of,
                    "strengths": resp.strengths,
                    "weaknesses": resp.weaknesses,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Update debate metrics 
            debate_metrics = self._calculate_debate_metrics(new_responses, prev_responses=current_responses)
            
            # After first round, don't force debate anymore
            if round_num >= self.min_debate_rounds:
                force_debate = False
            
            # Check for convergence
            convergence = self._check_convergence(current_responses, new_responses)
            if round_num > self.min_debate_rounds and convergence > 0.8:
                logger.info(f"High convergence detected ({convergence:.2f}). Ending debate.")
                break
            
            current_responses = new_responses
            
            # Publish round completion event
            if redis_client:
                await redis_client.publish(
                    "ai_council:debate", 
                    json.dumps({
                        "round": round_num,
                        "status": "completed",
                        "responses": [r.to_dict() for r in current_responses],
                        "convergence": convergence,
                        "timestamp": datetime.now().isoformat()
                    })
                )
        
        # After all rounds, check for partial consensus on topics
        if self.topic_extraction_enabled:
            key_points = self._extract_key_points(current_responses)
            consensus_points, dissent_points = self._categorize_key_points(key_points, current_responses)
            
            if consensus_points and len(consensus_points) > len(dissent_points):
                logger.info(f"Partial consensus detected with {len(consensus_points)} agreed points")
                result = self._build_partial_consensus_result(current_responses, debate_metrics, consensus_points, dissent_points)
                result.reconciliation_rounds = reconciliation_rounds
                return result
        
        # If we get here, we've hit max rounds or convergence threshold without full consensus
        logger.info(f"Max debate rounds reached without consensus. Using majority decision.")
        result = self._build_majority_decision(current_responses, debate_metrics)
        result.reconciliation_rounds = reconciliation_rounds
        return result
    
    async def _run_reconciliation_round(self, 
                                  current_responses: List[AgentResponse], 
                                  round_num: int,
                                  query: Optional[str] = None,
                                  redis_client = None) -> List[AgentResponse]:
        """
        Run a single round of reconciliation, generating critiques and updates.
        In a real implementation, this would call the actual AI models.
        """
        # In production, this would make real API calls to the agents
        # For demonstration, we'll simulate the responses
        
        new_responses = []
        
        # For each agent, generate a response that critiques others
        for i, agent_resp in enumerate(current_responses):
            # Get responses from other agents to critique
            other_responses = [r for r in current_responses if r.agent_id != agent_resp.agent_id]
            
            # In production, generate a critique prompt and call the agent API
            # For demo purposes, simulate the critique and response
            
            # Simulate strengths and weaknesses identified
            strengths = []
            weaknesses = []
            
            for other in other_responses:
                # Simulate finding strengths (in real impl, these would come from model)
                if other.confidence > 0.7:
                    strengths.append(f"Strong confidence in {other.agent_id}'s approach")
                if len(other.content) > 200:
                    strengths.append(f"Comprehensive explanation from {other.agent_id}")
                    
                # Simulate finding weaknesses
                if other.confidence < 0.6:
                    weaknesses.append(f"Low confidence in {other.agent_id}'s response")
                if "uncertain" in other.content.lower() or "possibly" in other.content.lower():
                    weaknesses.append(f"Uncertainty in {other.agent_id}'s reasoning")
            
            # Simulate confidence changes based on round
            # Later rounds tend toward convergence with highest confidence response
            if round_num > 1:
                # Find highest confidence response
                highest = max(current_responses, key=lambda r: r.confidence)
                
                # Agents tend to move toward the highest confidence view
                # Confidence gets adjusted based on how close they are to highest
                content_similarity = self._simulate_content_similarity(
                    agent_resp.content, highest.content
                )
                
                # If this is the highest confidence response, maintain confidence 
                # Otherwise adjust based on similarity to highest
                if agent_resp.agent_id == highest.agent_id:
                    adjusted_confidence = agent_resp.confidence * 0.95  # Slight decrease as they consider alternatives
                else:
                    # More similar responses get confidence boost
                    confidence_boost = content_similarity * 0.2
                    adjusted_confidence = agent_resp.confidence * 0.8 + confidence_boost
                
                # Simulate content becoming more similar to highest confidence
                content_blend_ratio = min(0.3 + (round_num * 0.15), 0.7)  # Increases with rounds
                blended_content = self._simulate_content_blending(
                    agent_resp.content, 
                    highest.content,
                    blend_ratio=content_blend_ratio
                )
                
                new_reasoning = f"After considering feedback from round {round_num}, " + \
                                f"I've incorporated insights from {', '.join([r.agent_id for r in other_responses])}."
                
                # Create the new response
                new_responses.append(
                    AgentResponse(
                        agent_id=agent_resp.agent_id,
                        content=blended_content,
                        confidence=adjusted_confidence,
                        reasoning=new_reasoning,
                        metadata={"debate_round": round_num, **agent_resp.metadata},
                        critique_of=[r.agent_id for r in other_responses],
                        strengths=strengths,
                        weaknesses=weaknesses,
                        round_num=round_num
                    )
                )
            else:
                # First round - critique but maintain position with slight adjustments
                adjusted_content = agent_resp.content
                
                # Make small modifications based on others' inputs
                if len(other_responses) > 0:
                    # Add a sentence acknowledging other viewpoints
                    adjusted_content += f"\n\nI've considered the perspectives of {', '.join([r.agent_id for r in other_responses])}."
                
                new_responses.append(
                    AgentResponse(
                        agent_id=agent_resp.agent_id,
                        content=adjusted_content,
                        confidence=agent_resp.confidence * 0.95,  # Slight decrease as they consider alternatives
                        reasoning=f"I've reviewed other agents' responses but largely maintain my position with small adjustments.",
                        metadata={"debate_round": round_num, **agent_resp.metadata},
                        critique_of=[r.agent_id for r in other_responses],
                        strengths=strengths,
                        weaknesses=weaknesses,
                        round_num=round_num
                    )
                )
            
            # In a real implementation, would publish critique events
            if redis_client:
                await redis_client.publish(
                    "ai_council:critique", 
                    json.dumps({
                        "round": round_num,
                        "agent": agent_resp.agent_id,
                        "critiquing": [r.agent_id for r in other_responses],
                        "strengths_identified": strengths,
                        "weaknesses_identified": weaknesses,
                        "timestamp": datetime.now().isoformat()
                    })
                )
                
                # Small delay to prevent message flood
                await asyncio.sleep(0.1)
                
        return new_responses
    
    def _simulate_content_similarity(self, content1: str, content2: str) -> float:
        """
        Simulate content similarity between two texts.
        In a real implementation, this would use embeddings or other NLP techniques.
        """
        # Simple word overlap for simulation
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        # Jaccard similarity
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union
    
    def _simulate_content_blending(self, 
                                 content1: str, 
                                 content2: str, 
                                 blend_ratio: float = 0.3) -> str:
        """
        Simulate blending two content pieces.
        content1 is the base content, content2 is the content to blend in.
        blend_ratio controls how much of content2 is incorporated.
        """
        # For demo purposes, do a simple text blend
        # In real NLP, this would use more sophisticated techniques
        
        # Split into sentences
        sentences1 = re.split(r'(?<=[.!?])\s+', content1)
        sentences2 = re.split(r'(?<=[.!?])\s+', content2)
        
        # Calculate how many sentences to take from content2
        num_sentences_to_blend = int(len(sentences1) * blend_ratio)
        
        # Select sentences from content2 to incorporate
        if len(sentences2) <= num_sentences_to_blend:
            sentences_to_add = sentences2
        else:
            # Take evenly distributed sentences
            step = len(sentences2) / num_sentences_to_blend
            indices = [int(i * step) for i in range(num_sentences_to_blend)]
            sentences_to_add = [sentences2[i] for i in indices if i < len(sentences2)]
        
        # Interleave sentences
        result = []
        for i, sentence in enumerate(sentences1):
            result.append(sentence)
            # Every few sentences, add one from content2
            if i % 3 == 0 and sentences_to_add:
                result.append(sentences_to_add.pop(0))
        
        # Add any remaining sentences from content2
        result.extend(sentences_to_add)
        
        return " ".join(result)
    
    def _has_consensus(self, responses: List[AgentResponse]) -> bool:
        """Enhanced consensus detection using content similarity."""
        if len(responses) <= 1:
            return True
            
        # Calculate pairwise similarities
        similarities = []
        for i, resp1 in enumerate(responses):
            for j in range(i+1, len(responses)):
                resp2 = responses[j]
                sim = self._simulate_content_similarity(resp1.content, resp2.content)
                similarities.append(sim)
        
        # Average similarity across all pairs
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0
        
        # Check for consensus
        return avg_similarity > (1.0 - self.consensus_threshold)
    
    def _has_strong_confidence(self, 
                              responses: List[AgentResponse], 
                              highest: AgentResponse) -> bool:
        """
        Check if the highest confidence response exceeds others
        by the confidence threshold.
        """
        # Get second highest confidence
        sorted_by_conf = sorted(responses, key=lambda r: r.confidence, reverse=True)
        if len(sorted_by_conf) < 2:
            return True
            
        second_highest = sorted_by_conf[1]
        
        # Check differential
        return highest.confidence - second_highest.confidence > self.confidence_threshold
    
    def _check_convergence(self, 
                         prev_responses: List[AgentResponse],
                         new_responses: List[AgentResponse]) -> float:
        """
        Measure how much convergence is happening between rounds.
        Returns a value between 0 (no convergence) and 1 (full convergence).
        """
        if not prev_responses or not new_responses:
            return 0.0
            
        # Map responses by agent ID for comparison
        prev_by_agent = {r.agent_id: r for r in prev_responses}
        new_by_agent = {r.agent_id: r for r in new_responses}
        
        # Only compare agents present in both rounds
        common_agents = set(prev_by_agent.keys()).intersection(set(new_by_agent.keys()))
        if not common_agents:
            return 0.0
            
        # Calculate convergence metrics
        content_similarities = []
        confidence_changes = []
        
        for agent in common_agents:
            prev = prev_by_agent[agent]
            new = new_by_agent[agent]
            
            # Content similarity
            sim = self._simulate_content_similarity(prev.content, new.content)
            content_similarities.append(sim)
            
            # Confidence change (absolute value)
            conf_change = abs(prev.confidence - new.confidence)
            confidence_changes.append(conf_change)
        
        # Average content similarity
        avg_content_sim = sum(content_similarities) / len(content_similarities)
        
        # Average confidence stability (1 = no change, 0 = max change)
        avg_conf_stability = 1.0 - min(1.0, sum(confidence_changes) / len(confidence_changes) * 5)
        
        # Combined convergence score (weighted)
        convergence = (avg_content_sim * 0.7) + (avg_conf_stability * 0.3)
        
        return convergence
    
    def _calculate_debate_metrics(self, 
                                responses: List[AgentResponse],
                                prev_responses: Optional[List[AgentResponse]] = None) -> DebateMetrics:
        """
        Calculate comprehensive metrics about the debate.
        """
        metrics = DebateMetrics()
        
        if not responses:
            return metrics
            
        # Calculate confidence stats
        confidences = [r.confidence for r in responses]
        metrics.average_confidence = sum(confidences) / len(confidences)
        metrics.confidence_spread = max(confidences) - min(confidences)
        
        # Calculate content variation
        # In a real impl, would use embedding similarity clusters
        # For demo, use simple text similarity
        unique_contents = set()
        for resp in responses:
            # Use a hash of the content as a proxy for uniqueness
            content_hash = hash(resp.content[:100])  # First 100 chars as fingerprint
            unique_contents.add(content_hash)
        
        metrics.response_variations = len(unique_contents)
        
        # Calculate cross-references
        cross_refs = 0
        for resp in responses:
            if resp.critique_of:
                cross_refs += len(resp.critique_of)
        metrics.cross_references = cross_refs
        
        # Calculate critique depth (mock implementation)
        if any(resp.strengths or resp.weaknesses for resp in responses):
            # Average number of strengths/weaknesses identified
            strength_counts = [len(resp.strengths) if resp.strengths else 0 for resp in responses]
            weakness_counts = [len(resp.weaknesses) if resp.weaknesses else 0 for resp in responses]
            
            avg_points = (sum(strength_counts) + sum(weakness_counts)) / (len(responses) * 2)
            metrics.critique_depth = min(10.0, avg_points * 2.5)  # Scale to 0-10
        
        # Calculate convergence rate if we have previous responses
        if prev_responses:
            metrics.convergence_rate = self._check_convergence(prev_responses, responses)
        
        # Calculate disagreement level
        # For demo: use confidence spread and response variations as proxy
        metrics.disagreement_level = min(1.0, (metrics.confidence_spread * 0.7) + 
                                         (metrics.response_variations / len(responses) * 0.3))
        
        return metrics
    
    def _extract_key_points(self, responses: List[AgentResponse]) -> Dict[str, List[str]]:
        """
        Extract key points from all responses and group by agent.
        In a real implementation, this would use NLP techniques.
        For demo, we'll simulate by extracting sentences with key phrases.
        """
        key_point_indicators = [
            "key point", "important", "critical", "essential", "significant",
            "must", "should", "primary", "fundamental", "crucial"
        ]
        
        key_points_by_agent = {}
        
        for resp in responses:
            # Extract sentences 
            sentences = re.split(r'(?<=[.!?])\s+', resp.content)
            
            # Find sentences with key point indicators
            agent_points = []
            for sentence in sentences:
                if any(indicator in sentence.lower() for indicator in key_point_indicators):
                    agent_points.append(sentence.strip())
            
            # If no key points found using indicators, use first 2-3 sentences
            if not agent_points and len(sentences) > 0:
                agent_points = [s.strip() for s in sentences[:min(3, len(sentences))]]
            
            key_points_by_agent[resp.agent_id] = agent_points
        
        return key_points_by_agent
    
    def _categorize_key_points(self, 
                             key_points: Dict[str, List[str]], 
                             responses: List[AgentResponse]) -> Tuple[List[str], List[str]]:
        """
        Categorize key points into consensus points and dissent points.
        """
        # Flatten all points for comparison
        all_points = []
        for agent, points in key_points.items():
            for point in points:
                all_points.append((agent, point))
        
        # Group similar points (in real impl, use semantic similarity)
        # For demo, use simple word overlap
        grouped_points = []
        for agent, point in all_points:
            found_group = False
            for group in grouped_points:
                # Check if this point is similar to the first point in the group
                _, first_point = group[0]
                if self._simulate_content_similarity(point, first_point) > 0.3:
                    group.append((agent, point))
                    found_group = True
                    break
            
            if not found_group:
                grouped_points.append([(agent, point)])
        
        # Identify consensus vs dissent points
        consensus_points = []
        dissent_points = []
        
        # To be consensus, more than half of agents should agree
        threshold = len(responses) / 2
        
        for group in grouped_points:
            agents_in_group = set(agent for agent, _ in group)
            if len(agents_in_group) > threshold:
                # Use the point from the highest confidence agent
                agent_confidences = {r.agent_id: r.confidence for r in responses}
                best_agent = max(agents_in_group, key=lambda a: agent_confidences.get(a, 0))
                
                # Find this agent's version of the point
                for a, p in group:
                    if a == best_agent:
                        consensus_points.append(p)
                        break
            else:
                # Add all variations as dissent points
                for _, point in group:
                    if point not in dissent_points:
                        dissent_points.append(point)
        
        return consensus_points, dissent_points
    
    def _build_consensus_result(self, 
                              responses: List[AgentResponse],
                              debate_metrics: DebateMetrics) -> ArbitrationResult:
        """Build result object for consensus case."""
        # Use the response with highest confidence for the content
        best_response = max(responses, key=lambda r: r.confidence)
        
        return ArbitrationResult(
            status=ResponseStatus.CONSENSUS,
            content=best_response.content,
            confidence=best_response.confidence,
            contributing_agents=[r.agent_id for r in responses],
            debate_log=self.debate_log,
            debate_metrics=debate_metrics
        )
    
    def _build_strong_confidence_result(self, 
                                      responses: List[AgentResponse],
                                      highest: AgentResponse,
                                      debate_metrics: DebateMetrics) -> ArbitrationResult:
        """Build result object for strong confidence differential case."""
        # Get the second highest for dissenting view
        sorted_by_conf = sorted(responses, key=lambda r: r.confidence, reverse=True)
        dissenting_view = None
        dissenting_agents = None
        
        if len(sorted_by_conf) > 1:
            second_highest = sorted_by_conf[1]
            dissenting_view = second_highest.content
            dissenting_agents = [second_highest.agent_id]
        
        return ArbitrationResult(
            status=ResponseStatus.STRONG_CONFIDENCE,
            content=highest.content,
            confidence=highest.confidence,
            contributing_agents=[highest.agent_id],
            debate_log=self.debate_log,
            debate_metrics=debate_metrics,
            dissenting_view=dissenting_view,
            dissenting_agents=dissenting_agents
        )
    
    def _build_partial_consensus_result(self,
                                      responses: List[AgentResponse],
                                      debate_metrics: DebateMetrics,
                                      consensus_points: List[str],
                                      dissent_points: List[str]) -> ArbitrationResult:
        """Build result for partial consensus case."""
        # Use highest confidence response as base
        best_response = max(responses, key=lambda r: r.confidence)
        
        # Format the consensus points into a cohesive response
        content = f"Based on our collaborative analysis, we have consensus on the following key points:\n\n"
        for i, point in enumerate(consensus_points, 1):
            content += f"{i}. {point}\n"
        
        if dissent_points:
            content += f"\n\nHowever, there are points of disagreement:\n\n"
            for i, point in enumerate(dissent_points, 1):
                content += f"{i}. {point}\n"
        
        # Determine contributing vs dissenting agents
        # For demo: if an agent's confidence is above average, they're contributing
        avg_confidence = sum(r.confidence for r in responses) / len(responses)
        contributing = [r.agent_id for r in responses if r.confidence >= avg_confidence]
        dissenting = [r.agent_id for r in responses if r.confidence < avg_confidence]
        
        return ArbitrationResult(
            status=ResponseStatus.PARTIAL_CONSENSUS,
            content=content,
            confidence=best_response.confidence * 0.9,  # Slightly lower confidence for partial consensus
            contributing_agents=contributing,
            debate_log=self.debate_log,
            debate_metrics=debate_metrics,
            dissenting_agents=dissenting,
            key_points_consensus=consensus_points,
            key_points_dissent=dissent_points)