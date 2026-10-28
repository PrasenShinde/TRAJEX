"""
Synthetic Vehicle Re-ID Embedding Module.

Generates noisy appearance embeddings for camera detections from a
vehicle's ground-truth embedding.  Calculates cosine similarity
between candidate sightings.

IMPORTANT: These are synthetic Re-ID embeddings, NOT embeddings
produced by a trained computer-vision model.  The module is designed
so that a pretrained Re-ID model can replace ``generate_noisy_embedding``
and ``compute_similarity`` in a future version.
"""

from typing import List, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine


class SyntheticReID:
    """
    Synthetic Re-ID embedding generator and similarity scorer.
    """

    def __init__(
        self,
        noise_level: float = 0.15,
        embedding_dim: int = 128,
        seed: int = 42,
    ) -> None:
        """
        Args:
            noise_level: Standard deviation of Gaussian noise added to
                         the ground-truth embedding at each sighting.
            embedding_dim: Dimensionality of the embedding vector.
            seed: Random seed for reproducibility.
        """
        self.noise_level = noise_level
        self.embedding_dim = embedding_dim
        self.rng = np.random.default_rng(seed)

    # ── Embedding generation ────────────────────────────────────────────

    def generate_noisy_embedding(
        self, ground_truth_embedding: np.ndarray
    ) -> np.ndarray:
        """
        Create a noisy version of a ground-truth embedding to simulate
        a camera sighting's appearance descriptor.

        The output is L2-normalised.
        """
        noise = self.rng.normal(0, self.noise_level, size=ground_truth_embedding.shape)
        noisy = ground_truth_embedding + noise
        norm = np.linalg.norm(noisy)
        if norm > 0:
            noisy /= norm
        return noisy.astype(np.float32)

    def generate_random_embedding(self) -> np.ndarray:
        """Generate a completely random normalised embedding."""
        vec = self.rng.normal(0, 1, size=self.embedding_dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    # ── Similarity ──────────────────────────────────────────────────────

    @staticmethod
    def compute_similarity(
        embedding_a: np.ndarray, embedding_b: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Returns:
            Similarity in [-1, 1], where 1 means identical direction.
        """
        a = np.asarray(embedding_a, dtype=float).reshape(-1)
        b = np.asarray(embedding_b, dtype=float).reshape(-1)
        if a.size == 0 or a.shape != b.shape:
            return 0.0
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        denominator = norm_a * norm_b
        if denominator == 0.0:
            return 0.0
        return float(np.clip(np.dot(a, b) / denominator, -1.0, 1.0))

    @staticmethod
    def compute_similarity_matrix(
        embeddings_a: np.ndarray, embeddings_b: np.ndarray
    ) -> np.ndarray:
        """
        Compute pairwise cosine similarity between two sets of embeddings.

        Args:
            embeddings_a: shape (N, D)
            embeddings_b: shape (M, D)

        Returns:
            Similarity matrix of shape (N, M).
        """
        return sk_cosine(embeddings_a, embeddings_b)

    # ── Batch helpers ───────────────────────────────────────────────────

    def add_noise_batch(
        self, embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Add noise to a batch of embeddings. Each row is treated independently.

        Args:
            embeddings: shape (N, D)

        Returns:
            Noisy embeddings of the same shape, each row L2-normalised.
        """
        noise = self.rng.normal(0, self.noise_level, size=embeddings.shape)
        noisy = embeddings + noise
        norms = np.linalg.norm(noisy, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1.0)
        return (noisy / norms).astype(np.float32)
