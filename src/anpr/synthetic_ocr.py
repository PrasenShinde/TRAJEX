"""
Synthetic OCR / ANPR Simulation Module.

Generates recognised number-plate strings from ground-truth plates by
introducing configurable character-level recognition errors, partial
readability, and OCR confidence scores.

IMPORTANT: No actual OCR is performed.  This module is a synthetic
simulation designed so that a real pretrained OCR model can replace it
in a future version.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np


# Characters that are commonly confused by OCR systems
_CONFUSION_MAP = {
    "0": ["O", "Q", "D"],
    "O": ["0", "Q", "D"],
    "1": ["I", "L", "7"],
    "I": ["1", "L"],
    "L": ["1", "I"],
    "2": ["Z"],
    "Z": ["2"],
    "5": ["S"],
    "S": ["5"],
    "8": ["B"],
    "B": ["8"],
    "6": ["G"],
    "G": ["6"],
    "D": ["0", "O"],
    "Q": ["0", "O"],
    "7": ["1"],
}


@dataclass
class OCRResult:
    """Result of a single synthetic OCR recognition."""
    recognised_plate: str
    confidence: float              # Overall OCR confidence [0, 1]
    char_confidences: List[float]  # Per-character confidences
    is_partial: bool               # True if some characters are unreadable
    num_errors: int                # Number of character substitutions introduced
    hypotheses: List[Tuple[str, float]]  # Alternative plate readings with scores


class SyntheticOCR:
    """
    Synthetic OCR engine that simulates number-plate recognition errors.

    Designed as a drop-in replacement target: a real OCR model should
    expose the same ``recognise()`` interface.
    """

    def __init__(
        self,
        error_rate: float = 0.15,
        partial_rate: float = 0.05,
        seed: int = 42,
    ) -> None:
        """
        Args:
            error_rate: Probability that any single character is misread.
            partial_rate: Probability that the plate is only partially readable.
            seed: Random seed for reproducibility.
        """
        self.error_rate = error_rate
        self.partial_rate = partial_rate
        self.rng = np.random.default_rng(seed)

    def recognise(self, ground_truth_plate: str) -> OCRResult:
        """
        Simulate OCR recognition of a number plate.

        Args:
            ground_truth_plate: The true plate string.

        Returns:
            An OCRResult with the (possibly corrupted) recognised plate,
            confidence, and alternative hypotheses.
        """
        chars = list(ground_truth_plate)
        recognised = []
        char_confs = []
        num_errors = 0
        is_partial = False

        # Decide if this is a partial read
        if self.rng.random() < self.partial_rate:
            is_partial = True
            # Mask 1–3 characters
            num_masked = self.rng.integers(1, min(4, len(chars) + 1))
            mask_positions = set(
                self.rng.choice(len(chars), size=num_masked, replace=False)
            )
        else:
            mask_positions = set()

        for i, ch in enumerate(chars):
            if i in mask_positions:
                recognised.append("?")
                char_confs.append(float(self.rng.uniform(0.05, 0.25)))
                num_errors += 1
                continue

            if self.rng.random() < self.error_rate:
                # Introduce a character-level error
                confused = _CONFUSION_MAP.get(ch.upper())
                if confused:
                    new_ch = self.rng.choice(confused)
                else:
                    # Random substitution
                    pool = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
                    new_ch = self.rng.choice(list(pool))
                recognised.append(new_ch)
                char_confs.append(float(self.rng.uniform(0.3, 0.7)))
                num_errors += 1
            else:
                recognised.append(ch)
                char_confs.append(float(self.rng.uniform(0.85, 0.99)))

        recognised_plate = "".join(recognised)

        # Overall confidence — geometric mean of char confidences
        if char_confs:
            overall_conf = float(np.exp(np.mean(np.log(
                np.clip(char_confs, 1e-6, 1.0)
            ))))
        else:
            overall_conf = 0.0

        # Generate alternative hypotheses
        hypotheses = self._generate_hypotheses(recognised_plate, overall_conf)

        return OCRResult(
            recognised_plate=recognised_plate,
            confidence=round(overall_conf, 4),
            char_confidences=[round(c, 4) for c in char_confs],
            is_partial=is_partial,
            num_errors=num_errors,
            hypotheses=hypotheses,
        )

    def recognise_multi_frame(
        self,
        ground_truth_plate: str,
        num_frames: int = 3,
    ) -> OCRResult:
        """
        Simulate multi-frame observation: run OCR on several 'frames' and
        fuse the results by majority vote per character position.

        Args:
            ground_truth_plate: The true plate string.
            num_frames: Number of simulated frames to fuse.

        Returns:
            A fused OCRResult with improved confidence.
        """
        frame_results = [self.recognise(ground_truth_plate) for _ in range(num_frames)]

        plate_len = len(ground_truth_plate)
        fused_chars = []
        fused_confs = []

        for pos in range(plate_len):
            votes: dict = {}
            confs_at_pos = []
            for fr in frame_results:
                if pos < len(fr.recognised_plate):
                    ch = fr.recognised_plate[pos]
                    conf = fr.char_confidences[pos] if pos < len(fr.char_confidences) else 0.5
                else:
                    ch = "?"
                    conf = 0.1
                votes[ch] = votes.get(ch, 0) + conf
                confs_at_pos.append(conf)

            best_char = max(votes, key=votes.get)
            best_conf = min(1.0, votes[best_char] / num_frames)
            fused_chars.append(best_char)
            fused_confs.append(best_conf)

        fused_plate = "".join(fused_chars)
        num_errors = sum(
            1 for a, b in zip(fused_plate, ground_truth_plate) if a != b
        )
        is_partial = "?" in fused_plate

        overall_conf = float(np.exp(np.mean(np.log(
            np.clip(fused_confs, 1e-6, 1.0)
        ))))

        hypotheses = self._generate_hypotheses(fused_plate, overall_conf)

        return OCRResult(
            recognised_plate=fused_plate,
            confidence=round(overall_conf, 4),
            char_confidences=[round(c, 4) for c in fused_confs],
            is_partial=is_partial,
            num_errors=num_errors,
            hypotheses=hypotheses,
        )

    # ── Plate comparison ────────────────────────────────────────────────

    @staticmethod
    def plate_similarity(
        plate_a: str,
        plate_b: str,
        conf_a: float = 1.0,
        conf_b: float = 1.0,
    ) -> float:
        """
        Confidence-aware character-level similarity between two plates.

        Args:
            plate_a, plate_b: Recognised plate strings.
            conf_a, conf_b: Overall OCR confidences.

        Returns:
            Similarity score in [0, 1].
        """
        if not plate_a or not plate_b:
            return 0.0

        max_len = max(len(plate_a), len(plate_b))
        if max_len == 0:
            return 1.0

        a_padded = plate_a.ljust(max_len, "?")
        b_padded = plate_b.ljust(max_len, "?")

        matches = 0
        comparisons = 0
        for ca, cb in zip(a_padded, b_padded):
            if ca == "?" or cb == "?":
                # Uncertain character — partial credit
                matches += 0.3
            elif ca == cb:
                matches += 1.0
            comparisons += 1

        raw_sim = matches / comparisons if comparisons > 0 else 0.0

        # Scale by the harmonic mean of confidences
        if conf_a + conf_b > 0:
            conf_weight = 2 * conf_a * conf_b / (conf_a + conf_b)
        else:
            conf_weight = 0.0

        # Blend: 70% raw similarity, 30% confidence-weighted
        return 0.7 * raw_sim + 0.3 * raw_sim * conf_weight

    # ── Private helpers ─────────────────────────────────────────────────

    def _generate_hypotheses(
        self, primary_plate: str, primary_conf: float
    ) -> List[Tuple[str, float]]:
        """Generate 1–3 alternative plate readings."""
        hypotheses = [(primary_plate, round(primary_conf, 4))]

        num_alt = self.rng.integers(0, 3)
        for _ in range(num_alt):
            alt_result = self._mutate_plate(primary_plate)
            alt_conf = max(0.1, primary_conf - self.rng.uniform(0.05, 0.25))
            hypotheses.append((alt_result, round(alt_conf, 4)))

        return hypotheses

    def _mutate_plate(self, plate: str) -> str:
        """Randomly change one character in the plate."""
        if not plate:
            return plate
        chars = list(plate)
        pos = self.rng.integers(0, len(chars))
        ch = chars[pos].upper()
        confused = _CONFUSION_MAP.get(ch)
        if confused:
            chars[pos] = self.rng.choice(confused)
        else:
            chars[pos] = self.rng.choice(list("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"))
        return "".join(chars)
