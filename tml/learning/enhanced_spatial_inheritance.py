"""
Enhanced Spatial Inheritance with Deep Learning Models
Advanced neural network-based spatial similarity and inheritance for TML Platform
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.manifold import TSNE
import pickle
import json
import time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from loguru import logger

from ..core.inheritance import SpatialInheritanceCoordinator


@dataclass
class SpatialEmbedding:
    """Represents a spatial embedding for a model"""
    model_id: str
    embedding: np.ndarray
    metadata: Dict[str, Any]
    performance_metrics: Dict[str, float]
    timestamp: float
    domain: str
    spatial_coordinates: Tuple[float, float]


@dataclass
class InheritanceCandidate:
    """Candidate model for inheritance"""
    model_id: str
    similarity_score: float
    embedding_distance: float
    performance_score: float
    inheritance_confidence: float
    metadata: Dict[str, Any]


class SpatialEmbeddingNetwork(nn.Module):
    """
    Deep neural network for learning spatial embeddings
    Maps model features to low-dimensional spatial representations
    """
    
    def __init__(self, input_dim: int, embedding_dim: int = 128, hidden_dims: List[int] = None):
        super(SpatialEmbeddingNetwork, self).__init__()
        
        if hidden_dims is None:
            hidden_dims = [256, 512, 256]
        
        self.input_dim = input_dim
        self.embedding_dim = embedding_dim
        
        # Build encoder network
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            prev_dim = hidden_dim
        
        # Final embedding layer
        layers.append(nn.Linear(prev_dim, embedding_dim))
        
        self.encoder = nn.Sequential(*layers)
        
        # Decoder for reconstruction loss
        decoder_layers = []
        prev_dim = embedding_dim
        
        for hidden_dim in reversed(hidden_dims):
            decoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            prev_dim = hidden_dim
        
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        self.decoder = nn.Sequential(*decoder_layers)
        
        # Contrastive learning head
        self.contrastive_head = nn.Sequential(
            nn.Linear(embedding_dim, embedding_dim // 2),
            nn.ReLU(),
            nn.Linear(embedding_dim // 2, embedding_dim)
        )
    
    def forward(self, x):
        embedding = self.encoder(x)
        reconstruction = self.decoder(embedding)
        contrastive_features = self.contrastive_head(embedding)
        
        return embedding, reconstruction, contrastive_features
    
    def encode(self, x):
        """Get embedding without reconstruction"""
        return self.encoder(x)


class ContrastiveLoss(nn.Module):
    """Contrastive loss for learning similar/dissimilar model representations"""
    
    def __init__(self, temperature: float = 0.1):
        super(ContrastiveLoss, self).__init__()
        self.temperature = temperature
    
    def forward(self, features, labels):
        """
        features: [batch_size, feature_dim]
        labels: [batch_size] - model domain labels
        """
        batch_size = features.shape[0]
        
        # Normalize features
        features = nn.functional.normalize(features, dim=1)
        
        # Compute similarity matrix
        similarity_matrix = torch.matmul(features, features.T) / self.temperature
        
        # Create positive mask (same domain)
        labels = labels.unsqueeze(1)
        positive_mask = torch.eq(labels, labels.T).float()
        
        # Remove diagonal (self-similarity)
        positive_mask.fill_diagonal_(0)
        
        # Compute contrastive loss
        exp_sim = torch.exp(similarity_matrix)
        sum_exp_sim = torch.sum(exp_sim, dim=1, keepdim=True)
        
        log_prob = similarity_matrix - torch.log(sum_exp_sim)
        
        # Average over positive pairs
        positive_log_prob = torch.sum(positive_mask * log_prob, dim=1)
        positive_count = torch.sum(positive_mask, dim=1)
        
        # Avoid division by zero
        positive_count = torch.clamp(positive_count, min=1.0)
        loss = -positive_log_prob / positive_count
        
        return torch.mean(loss)


class EnhancedSpatialInheritance:
    """
    Enhanced spatial inheritance using deep learning models
    Provides advanced neural network-based spatial similarity and inheritance
    """
    
    def __init__(self, embedding_dim: int = 128, device: str = None):
        self.embedding_dim = embedding_dim
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Neural network components
        self.embedding_network = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Spatial embeddings storage
        self.embeddings: Dict[str, SpatialEmbedding] = {}
        self.domain_embeddings: Dict[str, List[str]] = {}  # domain -> model_ids
        
        # Training parameters
        self.learning_rate = 0.001
        self.batch_size = 32
        self.epochs = 100
        self.patience = 10
        
        # Performance tracking
        self.training_history = []
        self.inheritance_stats = {
            'total_inheritances': 0,
            'successful_inheritances': 0,
            'avg_similarity_score': 0.0,
            'avg_performance_improvement': 0.0
        }
        
        logger.info(f"Enhanced Spatial Inheritance initialized on device: {self.device}")
    
    def extract_model_features(self, model_data: Dict[str, Any]) -> np.ndarray:
        """Extract comprehensive features from model data for embedding"""
        features = []
        
        # Performance metrics
        performance = model_data.get('performance', {})
        features.extend([
            performance.get('accuracy', 0.0),
            performance.get('precision', 0.0),
            performance.get('recall', 0.0),
            performance.get('f1_score', 0.0),
            performance.get('auc_roc', 0.0),
            performance.get('training_loss', 1.0),
            performance.get('validation_loss', 1.0)
        ])
        
        # Model architecture features
        architecture = model_data.get('architecture', {})
        features.extend([
            architecture.get('n_features', 0),
            architecture.get('n_layers', 0),
            architecture.get('n_parameters', 0),
            architecture.get('complexity_score', 0.0)
        ])
        
        # Data characteristics
        data_stats = model_data.get('data_statistics', {})
        features.extend([
            data_stats.get('n_samples', 0),
            data_stats.get('feature_variance', 0.0),
            data_stats.get('class_imbalance', 0.0),
            data_stats.get('noise_level', 0.0)
        ])
        
        # Spatial coordinates
        spatial_coords = model_data.get('spatial_coordinates', [0.0, 0.0])
        features.extend(spatial_coords)
        
        # Domain-specific features
        domain_features = model_data.get('domain_features', {})
        features.extend([
            domain_features.get('temporal_stability', 0.0),
            domain_features.get('feature_correlation', 0.0),
            domain_features.get('data_drift_score', 0.0),
            domain_features.get('concept_drift_score', 0.0)
        ])
        
        # Ensure consistent feature vector length
        target_length = 20  # Expected feature vector length
        if len(features) < target_length:
            features.extend([0.0] * (target_length - len(features)))
        elif len(features) > target_length:
            features = features[:target_length]
        
        return np.array(features, dtype=np.float32)
    
    def prepare_training_data(self) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Prepare training data from existing model embeddings"""
        if len(self.embeddings) < 10:
            raise ValueError("Need at least 10 models for training")
        
        features_list = []
        domain_labels = []
        performance_scores = []
        
        # Create domain label mapping
        unique_domains = list(set(emb.domain for emb in self.embeddings.values()))
        domain_to_idx = {domain: idx for idx, domain in enumerate(unique_domains)}
        
        for embedding in self.embeddings.values():
            # Extract features from metadata
            model_features = self.extract_model_features(embedding.metadata)
            features_list.append(model_features)
            
            # Domain label
            domain_labels.append(domain_to_idx[embedding.domain])
            
            # Performance score (for ranking)
            perf_score = np.mean(list(embedding.performance_metrics.values()))
            performance_scores.append(perf_score)
        
        # Convert to tensors
        features = torch.tensor(np.array(features_list), dtype=torch.float32)
        labels = torch.tensor(domain_labels, dtype=torch.long)
        scores = torch.tensor(performance_scores, dtype=torch.float32)
        
        # Normalize features
        features_np = features.numpy()
        features_normalized = self.scaler.fit_transform(features_np)
        features = torch.tensor(features_normalized, dtype=torch.float32)
        
        return features, labels, scores
    
    def train_embedding_network(self, features: torch.Tensor, labels: torch.Tensor, scores: torch.Tensor):
        """Train the spatial embedding network"""
        logger.info("Training spatial embedding network...")
        
        # Initialize network
        input_dim = features.shape[1]
        self.embedding_network = SpatialEmbeddingNetwork(
            input_dim=input_dim,
            embedding_dim=self.embedding_dim
        ).to(self.device)
        
        # Loss functions
        reconstruction_loss = nn.MSELoss()
        contrastive_loss = ContrastiveLoss()
        
        # Optimizer
        optimizer = optim.Adam(self.embedding_network.parameters(), lr=self.learning_rate)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)
        
        # Training data
        dataset = TensorDataset(features, labels, scores)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        # Training loop
        best_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(self.epochs):
            epoch_loss = 0.0
            self.embedding_network.train()
            
            for batch_features, batch_labels, batch_scores in dataloader:
                batch_features = batch_features.to(self.device)
                batch_labels = batch_labels.to(self.device)
                
                optimizer.zero_grad()
                
                # Forward pass
                embeddings, reconstructions, contrastive_features = self.embedding_network(batch_features)
                
                # Compute losses
                recon_loss = reconstruction_loss(reconstructions, batch_features)
                contrast_loss = contrastive_loss(contrastive_features, batch_labels)
                
                # Combined loss
                total_loss = recon_loss + 0.5 * contrast_loss
                
                # Backward pass
                total_loss.backward()
                optimizer.step()
                
                epoch_loss += total_loss.item()
            
            avg_loss = epoch_loss / len(dataloader)
            scheduler.step(avg_loss)
            
            # Early stopping
            if avg_loss < best_loss:
                best_loss = avg_loss
                patience_counter = 0
                # Save best model
                torch.save(self.embedding_network.state_dict(), 'best_embedding_model.pth')
            else:
                patience_counter += 1
                if patience_counter >= self.patience:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break
            
            # Log progress
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}: Loss = {avg_loss:.4f}")
            
            self.training_history.append({
                'epoch': epoch,
                'loss': avg_loss,
                'learning_rate': optimizer.param_groups[0]['lr']
            })
        
        # Load best model
        self.embedding_network.load_state_dict(torch.load('best_embedding_model.pth'))
        self.is_trained = True
        
        logger.info(f"Training completed. Best loss: {best_loss:.4f}")
    
    def compute_spatial_embedding(self, model_data: Dict[str, Any]) -> np.ndarray:
        """Compute spatial embedding for a model using trained network"""
        if not self.is_trained:
            raise ValueError("Embedding network not trained yet")
        
        # Extract features
        features = self.extract_model_features(model_data)
        
        # Normalize features
        features_normalized = self.scaler.transform(features.reshape(1, -1))
        
        # Convert to tensor
        features_tensor = torch.tensor(features_normalized, dtype=torch.float32).to(self.device)
        
        # Compute embedding
        self.embedding_network.eval()
        with torch.no_grad():
            embedding = self.embedding_network.encode(features_tensor)
            embedding_np = embedding.cpu().numpy().flatten()
        
        return embedding_np
    
    def add_model_embedding(self, model_id: str, model_data: Dict[str, Any]) -> SpatialEmbedding:
        """Add a new model embedding to the system"""
        # Compute embedding
        if self.is_trained:
            embedding_vector = self.compute_spatial_embedding(model_data)
        else:
            # Use traditional features if network not trained
            embedding_vector = self.extract_model_features(model_data)
        
        # Create spatial embedding
        spatial_embedding = SpatialEmbedding(
            model_id=model_id,
            embedding=embedding_vector,
            metadata=model_data,
            performance_metrics=model_data.get('performance', {}),
            timestamp=time.time(),
            domain=model_data.get('domain', 'unknown'),
            spatial_coordinates=tuple(model_data.get('spatial_coordinates', [0.0, 0.0]))
        )
        
        # Store embedding
        self.embeddings[model_id] = spatial_embedding
        
        # Update domain mapping
        domain = spatial_embedding.domain
        if domain not in self.domain_embeddings:
            self.domain_embeddings[domain] = []
        self.domain_embeddings[domain].append(model_id)
        
        logger.info(f"Added spatial embedding for model {model_id} in domain {domain}")
        
        return spatial_embedding
    
    def find_inheritance_candidates(self, target_model_id: str, 
                                  top_k: int = 5, 
                                  min_similarity: float = 0.3) -> List[InheritanceCandidate]:
        """Find the best inheritance candidates for a target model"""
        if target_model_id not in self.embeddings:
            raise ValueError(f"Model {target_model_id} not found in embeddings")
        
        target_embedding = self.embeddings[target_model_id]
        candidates = []
        
        for candidate_id, candidate_embedding in self.embeddings.items():
            if candidate_id == target_model_id:
                continue
            
            # Compute embedding similarity
            embedding_similarity = cosine_similarity(
                target_embedding.embedding.reshape(1, -1),
                candidate_embedding.embedding.reshape(1, -1)
            )[0, 0]
            
            # Compute spatial distance
            spatial_distance = np.linalg.norm(
                np.array(target_embedding.spatial_coordinates) - 
                np.array(candidate_embedding.spatial_coordinates)
            )
            
            # Compute performance score
            target_perf = np.mean(list(target_embedding.performance_metrics.values()))
            candidate_perf = np.mean(list(candidate_embedding.performance_metrics.values()))
            performance_score = candidate_perf / max(target_perf, 0.001)  # Avoid division by zero
            
            # Compute inheritance confidence
            domain_bonus = 1.2 if target_embedding.domain == candidate_embedding.domain else 1.0
            recency_bonus = 1.0 / (1.0 + (time.time() - candidate_embedding.timestamp) / 86400)  # Days
            
            inheritance_confidence = (
                embedding_similarity * 0.4 +
                (1.0 / (1.0 + spatial_distance)) * 0.3 +
                performance_score * 0.3
            ) * domain_bonus * recency_bonus
            
            if embedding_similarity >= min_similarity:
                candidate = InheritanceCandidate(
                    model_id=candidate_id,
                    similarity_score=embedding_similarity,
                    embedding_distance=1.0 - embedding_similarity,
                    performance_score=performance_score,
                    inheritance_confidence=inheritance_confidence,
                    metadata=candidate_embedding.metadata
                )
                candidates.append(candidate)
        
        # Sort by inheritance confidence
        candidates.sort(key=lambda x: x.inheritance_confidence, reverse=True)
        
        return candidates[:top_k]
    
    def perform_enhanced_inheritance(self, target_model_id: str, 
                                   source_model_id: str) -> Dict[str, Any]:
        """Perform enhanced inheritance between models"""
        if target_model_id not in self.embeddings or source_model_id not in self.embeddings:
            raise ValueError("Both models must exist in embeddings")
        
        target_embedding = self.embeddings[target_model_id]
        source_embedding = self.embeddings[source_model_id]
        
        # Compute inheritance weights based on embedding similarity
        similarity = cosine_similarity(
            target_embedding.embedding.reshape(1, -1),
            source_embedding.embedding.reshape(1, -1)
        )[0, 0]
        
        # Adaptive inheritance weights
        base_weight = min(0.8, max(0.1, similarity))
        
        # Performance-based adjustment
        target_perf = np.mean(list(target_embedding.performance_metrics.values()))
        source_perf = np.mean(list(source_embedding.performance_metrics.values()))
        
        if source_perf > target_perf:
            performance_boost = min(0.2, (source_perf - target_perf) / source_perf)
            inheritance_weight = min(0.9, base_weight + performance_boost)
        else:
            inheritance_weight = base_weight * 0.8
        
        # Create inheritance result
        inheritance_result = {
            'target_model_id': target_model_id,
            'source_model_id': source_model_id,
            'inheritance_weight': inheritance_weight,
            'similarity_score': similarity,
            'performance_improvement_estimate': (source_perf - target_perf) / max(target_perf, 0.001),
            'inheritance_confidence': inheritance_weight * similarity,
            'timestamp': time.time(),
            'method': 'enhanced_deep_learning'
        }
        
        # Update statistics
        self.inheritance_stats['total_inheritances'] += 1
        self.inheritance_stats['avg_similarity_score'] = (
            (self.inheritance_stats['avg_similarity_score'] * (self.inheritance_stats['total_inheritances'] - 1) + similarity) /
            self.inheritance_stats['total_inheritances']
        )
        
        logger.info(f"Enhanced inheritance: {source_model_id} -> {target_model_id} "
                   f"(weight: {inheritance_weight:.3f}, similarity: {similarity:.3f})")
        
        return inheritance_result
    
    def get_embedding_visualization(self) -> Dict[str, Any]:
        """Generate 2D visualization of model embeddings using t-SNE"""
        if len(self.embeddings) < 2:
            return {}
        
        # Collect embeddings and metadata
        embeddings_matrix = []
        model_ids = []
        domains = []
        performance_scores = []
        
        for model_id, embedding in self.embeddings.items():
            embeddings_matrix.append(embedding.embedding)
            model_ids.append(model_id)
            domains.append(embedding.domain)
            performance_scores.append(np.mean(list(embedding.performance_metrics.values())))
        
        embeddings_matrix = np.array(embeddings_matrix)
        
        # Apply t-SNE for 2D visualization
        tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(embeddings_matrix) - 1))
        embeddings_2d = tsne.fit_transform(embeddings_matrix)
        
        # Create visualization data
        visualization_data = {
            'embeddings_2d': embeddings_2d.tolist(),
            'model_ids': model_ids,
            'domains': domains,
            'performance_scores': performance_scores,
            'domain_colors': {domain: idx for idx, domain in enumerate(set(domains))},
            'timestamp': time.time()
        }
        
        return visualization_data
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'is_trained': self.is_trained,
            'total_embeddings': len(self.embeddings),
            'domains': list(self.domain_embeddings.keys()),
            'embedding_dimension': self.embedding_dim,
            'device': self.device,
            'inheritance_stats': self.inheritance_stats,
            'training_epochs': len(self.training_history),
            'last_training_loss': self.training_history[-1]['loss'] if self.training_history else None
        }
    
    def save_system_state(self, filepath: str):
        """Save the complete system state"""
        state = {
            'embeddings': {k: asdict(v) for k, v in self.embeddings.items()},
            'domain_embeddings': self.domain_embeddings,
            'inheritance_stats': self.inheritance_stats,
            'training_history': self.training_history,
            'scaler_state': pickle.dumps(self.scaler),
            'is_trained': self.is_trained,
            'embedding_dim': self.embedding_dim
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, default=str)
        
        # Save neural network if trained
        if self.is_trained and self.embedding_network:
            torch.save(self.embedding_network.state_dict(), filepath.replace('.json', '_network.pth'))
        
        logger.info(f"System state saved to {filepath}")
    
    def load_system_state(self, filepath: str):
        """Load the complete system state"""
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Restore embeddings
        self.embeddings = {}
        for model_id, embedding_dict in state['embeddings'].items():
            embedding_dict['embedding'] = np.array(embedding_dict['embedding'])
            self.embeddings[model_id] = SpatialEmbedding(**embedding_dict)
        
        self.domain_embeddings = state['domain_embeddings']
        self.inheritance_stats = state['inheritance_stats']
        self.training_history = state['training_history']
        self.is_trained = state['is_trained']
        self.embedding_dim = state['embedding_dim']
        
        # Restore scaler
        self.scaler = pickle.loads(state['scaler_state'].encode('latin-1'))
        
        # Load neural network if available
        network_path = filepath.replace('.json', '_network.pth')
        if self.is_trained and os.path.exists(network_path):
            input_dim = len(list(self.embeddings.values())[0].embedding) if self.embeddings else 20
            self.embedding_network = SpatialEmbeddingNetwork(
                input_dim=input_dim,
                embedding_dim=self.embedding_dim
            ).to(self.device)
            self.embedding_network.load_state_dict(torch.load(network_path, map_location=self.device))
        
        logger.info(f"System state loaded from {filepath}")


# Integration with existing TML system
class EnhancedSpatialInheritanceCoordinator(SpatialInheritanceCoordinator):
    """Enhanced coordinator that integrates deep learning spatial inheritance"""
    
    def __init__(self):
        super().__init__()
        self.enhanced_inheritance = EnhancedSpatialInheritance()
        self.auto_training_threshold = 50  # Train when we have 50+ models
        
    async def register_model_with_enhancement(self, model_id: str, model_data: Dict[str, Any]):
        """Register model with enhanced spatial inheritance"""
        # Add to enhanced system
        self.enhanced_inheritance.add_model_embedding(model_id, model_data)
        
        # Auto-train if we have enough models
        if (len(self.enhanced_inheritance.embeddings) >= self.auto_training_threshold and 
            not self.enhanced_inheritance.is_trained):
            await self._auto_train_embedding_network()
    
    async def _auto_train_embedding_network(self):
        """Automatically train the embedding network when enough data is available"""
        try:
            logger.info("Auto-training enhanced spatial inheritance network...")
            
            features, labels, scores = self.enhanced_inheritance.prepare_training_data()
            self.enhanced_inheritance.train_embedding_network(features, labels, scores)
            
            logger.info("✅ Enhanced spatial inheritance network trained successfully")
            
        except Exception as e:
            logger.error(f"Auto-training failed: {e}")
    
    def find_enhanced_inheritance_candidates(self, model_id: str, **kwargs):
        """Find inheritance candidates using enhanced deep learning approach"""
        if self.enhanced_inheritance.is_trained:
            return self.enhanced_inheritance.find_inheritance_candidates(model_id, **kwargs)
        else:
            # Fallback to traditional method
            return super().find_inheritance_candidates(model_id, **kwargs)
