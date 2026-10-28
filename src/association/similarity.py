"""
Similarity Scoring Module.

Provides individual similarity/compatibility scores for pairs of
detections across multiple evidence dimensions:

- Number-plate similarity (confidence-aware).
- Re-ID embedding cosine similarity.
- Vehicle type match.
- Vehicle colour match.
- Travel-direction compatibility.
- Timestamp difference score.

Each scorer returns a value normalised to [0, 1].
"""

from typing import Optional
import numpy as np

from src.anpr.synthetic_ocr import SyntheticOCR
from src.reid.synthetic_embeddings import SyntheticReID
from src.simulation.detection_generator import Detection


class SimilarityScorer:
    """
    Compute normalised component similarity scores between two detections.
    """

    # ── Plate similarity ────────────────────────────────────────────────

    @staticmethod
    def plate_similarity(det_a: Detection, det_b: Detection) -> float:
        """
        Confidence-aware plate similarity in [0, 1].
        """
        return SyntheticOCR.plate_similarity(
            det_a.recognised_plate,
            det_b.recognised_plate,
            det_a.ocr_confidence,
            det_b.ocr_confidence,
        )

    # ── Re-ID similarity ────────────────────────────────────────────────

    @staticmethod
    def reid_similarity(det_a: Detection, det_b: Detection) -> float:
        """
        Cosine similarity of Re-ID embeddings, mapped to [0, 1].
        Raw cosine is in [-1, 1]; we shift to [0, 1].
        """
        raw = SyntheticReID.compute_similarity(
            det_a.reid_embedding, det_b.reid_embedding
        )
        return float(np.clip((raw + 1.0) / 2.0, 0.0, 1.0))

    # ── Vehicle type match ──────────────────────────────────────────────

    @staticmethod
    def vehicle_type_match(det_a: Detection, det_b: Detection) -> float:
        """Return 1.0 if types match, 0.0 otherwise."""
        return 1.0 if det_a.vehicle_type == det_b.vehicle_type else 0.0

    # ── Colour match ────────────────────────────────────────────────────

    @staticmethod
    def colour_match(det_a: Detection, det_b: Detection) -> float:
        """Return 1.0 if colours match, 0.0 otherwise."""
        return 1.0 if det_a.vehicle_colour == det_b.vehicle_colour else 0.0

    # ── Direction compatibility ─────────────────────────────────────────

    _DIRECTION_ORDER = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    @classmethod
    def direction_compatibility(cls, det_a: Detection, det_b: Detection) -> float:
        """
        Soft compatibility score based on travel directions.
        Same direction = 1.0, opposite = 0.2, adjacent = 0.7, etc.
        """
        if det_a.travel_direction == det_b.travel_direction:
            return 1.0

        try:
            idx_a = cls._DIRECTION_ORDER.index(det_a.travel_direction)
            idx_b = cls._DIRECTION_ORDER.index(det_b.travel_direction)
        except ValueError:
            return 0.5  # Unknown direction

        diff = abs(idx_a - idx_b)
        diff = min(diff, 8 - diff)  # Circular distance

        # Map: 0→1.0, 1→0.8, 2→0.6, 3→0.3, 4→0.2
        scores = {0: 1.0, 1: 0.8, 2: 0.6, 3: 0.3, 4: 0.2}
        return scores.get(diff, 0.5)

    # ── Timestamp score ─────────────────────────────────────────────────

    @staticmethod
    def timestamp_score(
        det_a: Detection,
        det_b: Detection,
        max_gap_seconds: float = 7200.0,
    ) -> float:
        """
        Score based on elapsed time.  Returns 1.0 for short gaps,
        decays toward 0.0 as the gap approaches max_gap_seconds.
        Returns 0.0 for negative gaps (wrong temporal order).
        """
        elapsed = det_b.timestamp - det_a.timestamp
        if elapsed < 0:
            return 0.0
        if elapsed > max_gap_seconds:
            return 0.0
        # Exponential decay
        return float(np.exp(-elapsed / (max_gap_seconds / 3)))

    # ── Combined component dict ─────────────────────────────────────────

    @classmethod
    def compute_all(
        cls,
        det_a: Detection,
        det_b: Detection,
        max_gap_seconds: float = 7200.0,
    ) -> dict:
        """
        Compute all component scores and return as a dict.
        """
        return {
            "plate_similarity": cls.plate_similarity(det_a, det_b),
            "reid_similarity": cls.reid_similarity(det_a, det_b),
            "vehicle_type_match": cls.vehicle_type_match(det_a, det_b),
            "colour_match": cls.colour_match(det_a, det_b),
            "direction_match": cls.direction_compatibility(det_a, det_b),
            "timestamp_score": cls.timestamp_score(det_a, det_b, max_gap_seconds),
        }
