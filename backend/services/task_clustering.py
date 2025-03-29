import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.manifold import TSNE
import umap
from sentence_transformers import SentenceTransformer
import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Dict, Tuple, Any, Optional
import json
import datetime as dt
import matplotlib.colors as mcolors
import os
from collections import Counter

class TaskClusteringSystem:
    """
    Identifies task clusters based on complexity and content embeddings,
    then routes tasks to specialized agents based on historical performance.
    """
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        min_samples: int = 100,
        clustering_method: str = "kmeans",
        n_clusters: int = 5,
        visualization_path: str = "./visualizations",
    ):
        self.embedding_model = SentenceTransformer(embedding_model)
        self.min_samples = min_samples
        self.clustering_method = clustering_method
        self.n_clusters = n_clusters
        self.visualization_path = visualization_path
        self.cluster_model = None
        self.cluster_centers = None
        self.dimension_reducer = None
        
        # Tracking for agent performance by cluster
        self.agent_performance = {}
        
        # Ensure visualization directory exists
        os.makedirs(visualization_path, exist_ok=True)
    
    def extract_features(self, task_history: List[Dict]) -> Tuple[np.ndarray, List[Dict]]:
        """
        Extract features from task history for clustering.
        Returns feature matrix and metadata.
        """
        # Extract content for embedding
        contents = [task.get("content", "") for task in task_history]
        
        # Generate embeddings with sentence transformer
        content_embeddings = self.embedding_model.encode(contents)
        
        # Extract complexity scores and other numerical features
        complexity_scores = np.array([
            task.get("diagnostics", {}).get("complexity_score", 0) 
            for task in task_history
        ]).reshape(-1, 1)
        
        # Extract word counts
        word_counts = np.array([
            task.get("diagnostics", {}).get("word_count", 0) 
            for task in task_history
        ]).reshape(-1, 1)
        
        # Create category score features
        category_scores = np.array([
            [
                task.get("diagnostics", {}).get("category_scores", {}).get("analytical", 0),
                task.get("diagnostics", {}).get("category_scores", {}).get("comparative", 0),
                task.get("diagnostics", {}).get("category_scores", {}).get("creative", 0),
                task.get("diagnostics", {}).get("category_scores", {}).get("complex", 0)
            ]
            for task in task_history
        ])
        
        # Combine all features - must handle different dimensions properly
        # Normalize the embeddings since they'll dominate otherwise
        normalized_embeddings = content_embeddings / np.linalg.norm(content_embeddings, axis=1, keepdims=True)
        
        # Combine with other features - use np.hstack to combine horizontally
        feature_matrix = np.hstack([
            normalized_embeddings,  # Semantic understanding (dominant factor)
            complexity_scores * 0.5,  # Scaled complexity (important but not dominant)
            word_counts * 0.1,       # Word count is less important
            category_scores * 0.3    # Category scores provide context
        ])
        
        # Create metadata for visualization and analysis
        metadata = []
        for i, task in enumerate(task_history):
            meta = {
                "task_id": task.get("task_id", f"unknown-{i}"),
                "content": task.get("content", "")[:50] + "..." if len(task.get("content", "")) > 50 else task.get("content", ""),
                "complexity": task.get("diagnostics", {}).get("complexity_score", 0),
                "word_count": task.get("diagnostics", {}).get("word_count", 0),
                "reasoning_effort": task.get("reasoning_effort", "medium"),
                "agent": task.get("target_agent", "unknown"),
                "event": task.get("event", "unknown"),
                "duration": task.get("duration", 0),
                "successful": task.get("outcome", "") == "success"
            }
            metadata.append(meta)
        
        return feature_matrix, metadata
    
    def cluster_tasks(self, feature_matrix: np.ndarray) -> np.ndarray:
        """
        Cluster tasks based on features.
        Returns cluster assignments.
        """
        # Apply different clustering methods based on configuration
        if self.clustering_method == "kmeans":
            self.cluster_model = KMeans(n_clusters=self.n_clusters, random_state=42)
            clusters = self.cluster_model.fit_predict(feature_matrix)
            self.cluster_centers = self.cluster_model.cluster_centers_
            
        elif self.clustering_method == "dbscan":
            self.cluster_model = DBSCAN(eps=0.5, min_samples=5)
            clusters = self.cluster_model.fit_predict(feature_matrix)
            # DBSCAN doesn't have predefined centers
            self.cluster_centers = None
            
        else:
            raise ValueError(f"Unsupported clustering method: {self.clustering_method}")
        
        return clusters
    
    def visualize_clusters(self, feature_matrix: np.ndarray, clusters: np.ndarray, metadata: List[Dict], timestamp: str) -> str:
        """
        Visualize clusters using dimensionality reduction.
        Returns the path to the saved visualization.
        """
        # Use UMAP for dimensionality reduction
        self.dimension_reducer = umap.UMAP(n_components=2, random_state=42)
        reduced_features = self.dimension_reducer.fit_transform(feature_matrix)
        
        # Create a DataFrame for easier plotting
        df = pd.DataFrame({
            'x': reduced_features[:, 0],
            'y': reduced_features[:, 1],
            'cluster': clusters,
            'effort': [m['reasoning_effort'] for m in metadata],
            'complexity': [m['complexity'] for m in metadata],
            'word_count': [m['word_count'] for m in metadata],
            'content': [m['content'] for m in metadata],
            'agent': [m['agent'] for m in metadata],
            'successful': [m['successful'] for m in metadata]
        })
        
        # Set up the plot
        plt.figure(figsize=(12, 10))
        
        # Create a colormap for clusters
        cmap = plt.cm.get_cmap('tab10', len(np.unique(clusters)))
        
        # Plot by cluster
        scatter = plt.scatter(
            df['x'], df['y'], 
            c=df['cluster'], 
            cmap=cmap, 
            s=df['complexity']*30 + 10,  # Size based on complexity
            alpha=0.7,
            edgecolors='w'
        )
        
        # Add cluster centers if available
        if self.cluster_centers is not None and self.dimension_reducer is not None:
            # Transform cluster centers to 2D
            centers_2d = self.dimension_reducer.transform(self.cluster_centers)
            plt.scatter(
                centers_2d[:, 0], centers_2d[:, 1],
                marker='X', s=200, c='red', edgecolors='k'
            )
        
        # Add a colorbar legend
        cbar = plt.colorbar(scatter)
        cbar.set_label('Cluster')
        
        # Add a legend for reasoning effort
        effort_handles = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color, label=effort, markersize=10)
            for effort, color in zip(['low', 'medium', 'high'], ['green', 'orange', 'red'])
        ]
        plt.legend(handles=effort_handles, title="Reasoning Effort", loc='upper right')
        
        # Add title and labels
        plt.title('Task Clusters by Content, Complexity, and Features', fontsize=16)
        plt.xlabel('UMAP Dimension 1', fontsize=12)
        plt.ylabel('UMAP Dimension 2', fontsize=12)
        
        # Annotate a few points from each cluster for context
        cluster_ids = np.unique(clusters)
        for cluster_id in cluster_ids:
            cluster_points = df[df['cluster'] == cluster_id]
            if len(cluster_points) > 0:
                # Annotate up to 3 points per cluster
                for _, row in cluster_points.sample(min(3, len(cluster_points))).iterrows():
                    plt.annotate(
                        row['content'],
                        (row['x'], row['y']),
                        xytext=(5, 5),
                        textcoords='offset points',
                        fontsize=8,
                        alpha=0.8
                    )
        
        # Save the visualization
        file_path = f"{self.visualization_path}/task_clusters_{timestamp}.png"
        plt.tight_layout()
        plt.savefig(file_path, dpi=300)
        plt.close()
        
        return file_path
    
    def analyze_cluster_characteristics(self, clusters: np.ndarray, metadata: List[Dict]) -> Dict[int, Dict[str, Any]]:
        """
        Analyze the characteristics of each cluster.
        Returns a dictionary of cluster profiles.
        """
        cluster_ids = np.unique(clusters)
        cluster_profiles = {}
        
        for cluster_id in cluster_ids:
            # Get all tasks in this cluster
            cluster_indices = np.where(clusters == cluster_id)[0]
            cluster_tasks = [metadata[i] for i in cluster_indices]
            
            # Skip if empty
            if not cluster_tasks:
                continue
            
            # Calculate key metrics
            avg_complexity = np.mean([task['complexity'] for task in cluster_tasks])
            avg_word_count = np.mean([task['word_count'] for task in cluster_tasks])
            effort_counts = Counter([task['reasoning_effort'] for task in cluster_tasks])
            agent_counts = Counter([task['agent'] for task in cluster_tasks])
            success_rate = np.mean([1 if task['successful'] else 0 for task in cluster_tasks])
            
            # Get example tasks (first 3)
            examples = [task['content'] for task in cluster_tasks[:3]]
            
            # Create profile
            cluster_profiles[int(cluster_id)] = {
                'size': len(cluster_tasks),
                'avg_complexity': float(avg_complexity),
                'avg_word_count': float(avg_word_count),
                'effort_distribution': {k: v/len(cluster_tasks) for k, v in effort_counts.items()},
                'dominant_effort': max(effort_counts.items(), key=lambda x: x[1])[0] if effort_counts else "unknown",
                'agent_distribution': {k: v/len(cluster_tasks) for k, v in agent_counts.items()},
                'success_rate': float(success_rate),
                'examples': examples
            }
            
            # Calculate agent performance in this cluster
            for agent in set([task['agent'] for task in cluster_tasks]):
                agent_tasks = [task for task in cluster_tasks if task['agent'] == agent]
                if not agent_tasks:
                    continue
                
                agent_success = np.mean([1 if task['successful'] else 0 for task in agent_tasks])
                agent_duration = np.mean([task['duration'] for task in agent_tasks if task['duration'] > 0])
                
                # Store agent performance by cluster
                if agent not in self.agent_performance:
                    self.agent_performance[agent] = {}
                    
                self.agent_performance[agent][cluster_id] = {
                    'tasks_count': len(agent_tasks),
                    'success_rate': float(agent_success),
                    'avg_duration': float(agent_duration),
                    'cluster_match_score': float(agent_success * 0.7 + (1.0 / (agent_duration + 1)) * 0.3)
                }
        
        return cluster_profiles
    
    def determine_best_agent_per_cluster(self) -> Dict[int, str]:
        """
        Determine the best agent for each cluster based on performance.
        Returns a mapping of cluster ID to agent name.
        """
        best_agents = {}
        
        # For each cluster, find the agent with the best performance
        for cluster_id in set([c for agent_data in self.agent_performance.values() for c in agent_data.keys()]):
            best_score = -1
            best_agent = None
            
            for agent, clusters in self.agent_performance.items():
                if cluster_id in clusters and clusters[cluster_id]['tasks_count'] >= 5:  # Minimum sample size
                    score = clusters[cluster_id]['cluster_match_score']
                    if score > best_score:
                        best_score = score
                        best_agent = agent
            
            if best_agent:
                best_agents[cluster_id] = best_agent
        
        return best_agents
    
    def run_analysis(self, task_history: List[Dict]) -> Dict[str, Any]:
        """
        Run the complete clustering analysis pipeline.
        Returns the analysis results.
        """
        # Ensure we have enough data
        if len(task_history) < self.min_samples:
            return {
                "status": "insufficient_data",
                "message": f"Need at least {self.min_samples} samples, got {len(task_history)}"
            }
        
        # Generate timestamp for filenames
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Extract features
        feature_matrix, metadata = self.extract_features(task_history)
        
        # Cluster tasks
        clusters = self.cluster_tasks(feature_matrix)
        
        # Analyze cluster characteristics
        cluster_profiles = self.analyze_cluster_characteristics(clusters, metadata)
        
        # Determine the best agent for each cluster
        best_agents = self.determine_best_agent_per_cluster()
        
        # Visualize clusters
        visualization_path = self.visualize_clusters(feature_matrix, clusters, metadata, timestamp)
        
        # Prepare the results
        results = {
            "status": "success",
            "timestamp": dt.datetime.now().isoformat(),
            "total_tasks": len(task_history),
            "clusters_found": len(np.unique(clusters)),
            "cluster_profiles": cluster_profiles,
            "best_agents_by_cluster": best_agents,
            "visualization_path": visualization_path,
            "method": self.clustering_method
        }
        
        # Save results to file
        results_path = f"{self.visualization_path}/cluster_analysis_{timestamp}.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        return results
    
    def predict_cluster(self, task_content: str, complexity_score: float = 0.0, 
                      category_scores: Dict[str, float] = None) -> Optional[int]:
        """
        Predict which cluster a new task belongs to.
        Returns the cluster ID if a model is trained, otherwise None.
        """
        if self.cluster_model is None or self.embedding_model is None:
            return None
            
        # Default category scores if not provided
        if category_scores is None:
            category_scores = {
                "analytical": 0.0,
                "comparative": 0.0,
                "creative": 0.0,
                "complex": 0.0
            }
        
        # Generate embedding
        content_embedding = self.embedding_model.encode([task_content])[0]
        normalized_embedding = content_embedding / np.linalg.norm(content_embedding)
        
        # Create feature vector
        word_count = len(task_content.split())
        category_array = np.array([
            category_scores.get("analytical", 0),
            category_scores.get("comparative", 0),
            category_scores.get("creative", 0),
            category_scores.get("complex", 0)
        ])
        
        # Combine features in the same way as during training
        feature_vector = np.hstack([
            normalized_embedding.reshape(1, -1),
            np.array(complexity_score * 0.5).reshape(1, -1),
            np.array(word_count * 0.1).reshape(1, -1),
            category_array.reshape(1, -1) * 0.3
        ])
        
        # Predict cluster
        cluster = self.cluster_model.predict(feature_vector)[0]
        
        return int(cluster)
    
    def recommend_agent(self, task_content: str, complexity_score: float = 0.0,
                      category_scores: Dict[str, float] = None) -> Optional[str]:
        """
        Recommend the best agent for a new task based on its predicted cluster.
        Returns agent name or None if insufficient data.
        """
        # Predict the cluster
        cluster = self.predict_cluster(task_content, complexity_score, category_scores)
        
        if cluster is None:
            return None
            
        # Get the best agents by cluster
        best_agents = self.determine_best_agent_per_cluster()
        
        # Return the best agent for this cluster, or None if not found
        return best_agents.get(cluster)

class TaskRouter:
    """
    Routes tasks to the most appropriate agent based on cluster analysis
    and real-time performance metrics.
    """
    def __init__(
        self, 
        default_agent: str = "Grok",
        clustering_system: TaskClusteringSystem = None,
        learning_rate: float = 0.1,  # For exploration vs exploitation
        log_path: str = "./logs"
    ):
        self.default_agent = default_agent
        self.clustering_system = clustering_system or TaskClusteringSystem()
        self.learning_rate = learning_rate
        self.log_path = log_path
        
        # Performance tracking
        self.agent_stats = {}
        
        # Decision logging
        os.makedirs(log_path, exist_ok=True)
        self.decision_log = []
    
    def route_task(
        self, 
        task_id: str,
        content: str,
        available_agents: List[str],
        diagnostics: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Route a task to the most appropriate agent based on content and diagnostics.
        Returns the chosen agent name and routing metadata.
        """
        # Extract complexity score and category scores from diagnostics if available
        complexity_score = diagnostics.get("complexity_score", 0.0) if diagnostics else 0.0
        category_scores = diagnostics.get("category_scores", {}) if diagnostics else {}
        
        # Initialize routing decision with defaults
        routing_decision = {
            "task_id": task_id,
            "timestamp": dt.datetime.now().isoformat(),
            "method": "default",
            "chosen_agent": self.default_agent,
            "confidence": 0.5,
            "alternatives": {},
            "exploration": False
        }
        
        # If no agents available, return default
        if not available_agents:
            routing_decision["method"] = "default_only"
            routing_decision["chosen_agent"] = self.default_agent
            return self.default_agent, routing_decision
        
        # Check if we have a trained clustering system
        if self.clustering_system and hasattr(self.clustering_system, 'cluster_model') and self.clustering_system.cluster_model is not None:
            # Try to get cluster-based recommendation
            recommended_agent = self.clustering_system.recommend_agent(
                content, complexity_score, category_scores
            )
            
            if recommended_agent and recommended_agent in available_agents:
                routing_decision["method"] = "cluster_based"
                routing_decision["chosen_agent"] = recommended_agent
                routing_decision["confidence"] = 0.8
                routing_decision["cluster_recommendation"] = True
                
                # Random exploration with probability learning_rate
                if np.random.random() < self.learning_rate:
                    # Exclude the recommended agent
                    exploration_candidates = [a for a in available_agents if a != recommended_agent]
                    if exploration_candidates:
                        exploration_agent = np.random.choice(exploration_candidates)
                        routing_decision["chosen_agent"] = exploration_agent
                        routing_decision["exploration"] = True
                        routing_decision["original_recommendation"] = recommended_agent
                        
                self.log_routing_decision(routing_decision)
                return routing_decision["chosen_agent"], routing_decision
        
        # Fallback to performance-based routing if we have stats
        if self.agent_stats and all(agent in self.agent_stats for agent in available_agents):
            # Calculate a score for each agent based on success rate, speed, and availability
            agent_scores = {}
            for agent in available_agents:
                stats = self.agent_stats[agent]
                # Formula: 0.6 * success_rate + 0.4 * (1 / (normalized_duration + 1))
                score = (0.6 * stats.get("success_rate", 0.5) + 
                         0.4 * (1 / (stats.get("normalized_duration", 1.0) + 1)))
                agent_scores[agent] = score
            
            # Choose the agent with the highest score
            chosen_agent = max(agent_scores.items(), key=lambda x: x[1])[0]
            
            routing_decision["method"] = "performance_based"
            routing_decision["chosen_agent"] = chosen_agent
            routing_decision["confidence"] = 0.7
            routing_decision["alternatives"] = agent_scores
            
            # Random exploration with probability learning_rate
            if np.random.random() < self.learning_rate:
                # Exclude the top-performing agent
                exploration_candidates = [a for a in available_agents if a != chosen_agent]
                if exploration_candidates:
                    exploration_agent = np.random.choice(exploration_candidates)
                    routing_decision["chosen_agent"] = exploration_agent
                    routing_decision["exploration"] = True
                    routing_decision["original_recommendation"] = chosen_agent
                    
            self.log_routing_decision(routing_decision)
            return routing_decision["chosen_agent"], routing_decision
        
        # If all else fails, use round-robin or random assignment
        chosen_agent = np.random.choice(available_agents)
        
        routing_decision["method"] = "random"
        routing_decision["chosen_agent"] = chosen_agent
        routing_decision["confidence"] = 0.3
        
        self.log_routing_decision(routing_decision)
        return chosen_agent, routing_decision
    
    def update_agent_stats(self, agent: str, task_duration: float, success: bool):
        """
        Update agent performance statistics based on task results.
        """
        if agent not in self.agent_stats:
            self.agent_stats[agent] = {
                "tasks_completed": 0,
                "successful_tasks": 0,
                "total_duration": 0,
                "success_rate": 0.5,  # Initial neutral value
                "avg_duration": 0,
                "normalized_duration": 1.0  # Initial neutral value
            }
        
        # Update stats
        stats = self.agent_stats[agent]
        stats["tasks_completed"] += 1
        if success:
            stats["successful_tasks"] += 1
        stats["total_duration"] += task_duration
        
        # Recalculate derived metrics
        stats["success_rate"] = stats["successful_tasks"] / stats["tasks_completed"]
        stats["avg_duration"] = stats["total_duration"] / stats["tasks_completed"]
        
        # Calculate normalized duration across all agents
        avg_durations = [a["avg_duration"] for a in self.agent_stats.values() if a["tasks_completed"] > 0]
        if avg_durations:
            avg_overall = sum(avg_durations) / len(avg_durations)
            if avg_overall > 0:
                stats["normalized_duration"] = stats["avg_duration"] / avg_overall
    
    def log_routing_decision(self, decision: Dict[str, Any]):
        """
        Log routing decisions for analysis and improvement.
        """
        self.decision_log.append(decision)
        
        # Keep a rotating log file
        log_file = f"{self.log_path}/routing_decisions.jsonl"
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(decision) + '\n')
        except Exception as e:
            print(f"Error logging routing decision: {e}")
            
        # If we have too many decisions in memory, keep only the most recent ones
        if len(self.decision_log) > 1000:
            self.decision_log = self.decision_log[-1000:]

if __name__ == "__main__":
    # Example usage
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Load some sample task history
    try:
        with open("task_history.json", "r") as f:
            task_history = json.load(f)
    except FileNotFoundError:
        print("No task history found. Creating dummy data.")
        # Create dummy data
        task_history = []
        for i in range(200):
            task = {
                "task_id": f"task_{i}",
                "content": f"This is a sample task {i} for testing clustering",
                "reasoning_effort": np.random.choice(["low", "medium", "high"]),
                "target_agent": np.random.choice(["Grok", "Claude", "GPT"]),
                "event": np.random.choice(["plan", "execute", "complete"]),
                "diagnostics": {
                    "complexity_score": np.random.random() * 5,
                    "word_count": np.random.randint(5, 100),
                    "category_scores": {
                        "analytical": np.random.randint(0, 2),
                        "comparative": np.random.randint(0, 2),
                        "creative": np.random.randint(0, 2),
                        "complex": np.random.randint(0, 2)
                    }
                },
                "duration": np.random.randint(30, 600),
                "outcome": np.random.choice(["success", "failure"], p=[0.8, 0.2])
            }
            task_history.append(task)
    
    # Create clustering system
    clustering_system = TaskClusteringSystem(
        n_clusters=4,
        visualization_path="./cluster_viz"
    )
    
    # Run analysis
    results = clustering_system.run_analysis(task_history)
    print(f"Analysis complete: {results['status']}")
    print(f"Found {results['clusters_found']} clusters.")
    
    # Print cluster profiles
    for cluster_id, profile in results['cluster_profiles'].items():
        print(f"\nCluster {cluster_id}:")
        print(f"  Size: {profile['size']} tasks")
        print(f"  Avg Complexity: {profile['avg_complexity']:.2f}")
        print(f"  Dominant Effort: {profile['dominant_effort']}")
        print(f"  Success Rate: {profile['success_rate']:.2%}")
        print(f"  Examples: {profile['examples'][0]}")
    
    # Print agent recommendations
    print("\nBest Agents by Cluster:")
    for cluster_id, agent in results['best_agents_by_cluster'].items():
        print(f"  Cluster {cluster_id}: {agent}")
    
    # Create router
    router = TaskRouter(
        default_agent="Grok",
        clustering_system=clustering_system
    )
    
    # Test routing
    test_task = "Analyze this dataset and create a visualization of the trends."
    chosen_agent, decision = router.route_task(
        "test_task_1",
        test_task,
        ["Grok", "Claude", "GPT"],
        {
            "complexity_score": 3.5,
            "category_scores": {
                "analytical": 1,
                "creative": 1
            }
        }
    )
    
    print(f"\nRouting test task: '{test_task}'")
    print(f"Chosen agent: {chosen_agent}")
    print(f"Routing method: {decision['method']}")
    print(f"Confidence: {decision['confidence']:.2f}")
    if decision.get("exploration"):
        print(f"Exploration mode! Original recommendation: {decision['original_recommendation']}")