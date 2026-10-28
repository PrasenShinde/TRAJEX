"""
Tests for the Synthetic OCR Simulation module.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np
from src.anpr.synthetic_ocr import SyntheticOCR, OCRResult


class TestSyntheticOCR:
    """Tests for the SyntheticOCR class."""

    def setup_method(self):
        self.ocr = SyntheticOCR(error_rate=0.15, partial_rate=0.05, seed=42)

    def test_recognise_returns_ocr_result(self):
        result = self.ocr.recognise("DL01AB1234")
        assert isinstance(result, OCRResult)
        assert isinstance(result.recognised_plate, str)
        assert 0 <= result.confidence <= 1
        assert len(result.char_confidences) == len("DL01AB1234")

    def test_recognise_preserves_length(self):
        plate = "MH12CD5678"
        result = self.ocr.recognise(plate)
        assert len(result.recognised_plate) == len(plate)

    def test_zero_error_rate_preserves_plate(self):
        ocr_perfect = SyntheticOCR(error_rate=0.0, partial_rate=0.0, seed=42)
        plate = "KA03EF9012"
        result = ocr_perfect.recognise(plate)
        assert result.recognised_plate == plate
        assert result.num_errors == 0

    def test_high_error_rate_introduces_errors(self):
        ocr_noisy = SyntheticOCR(error_rate=0.9, partial_rate=0.0, seed=42)
        plate = "TN04GH3456"
        result = ocr_noisy.recognise(plate)
        assert result.num_errors > 0

    def test_partial_plate(self):
        ocr_partial = SyntheticOCR(error_rate=0.0, partial_rate=1.0, seed=42)
        result = ocr_partial.recognise("UP05IJ7890")
        assert result.is_partial
        assert "?" in result.recognised_plate

    def test_hypotheses_generated(self):
        result = self.ocr.recognise("RJ06KL2345")
        assert len(result.hypotheses) >= 1
        assert result.hypotheses[0][0] == result.recognised_plate

    def test_multi_frame_recognition(self):
        result = self.ocr.recognise_multi_frame("DL07MN6789", num_frames=5)
        assert isinstance(result, OCRResult)
        assert len(result.recognised_plate) == len("DL07MN6789")

    def test_plate_similarity_identical(self):
        sim = SyntheticOCR.plate_similarity("DL01AB1234", "DL01AB1234")
        assert sim > 0.9

    def test_plate_similarity_different(self):
        sim = SyntheticOCR.plate_similarity("DL01AB1234", "MH99ZZ9999")
        assert sim < 0.5

    def test_plate_similarity_partial(self):
        sim = SyntheticOCR.plate_similarity("DL01??1234", "DL01AB1234")
        assert 0 < sim < 1

    def test_plate_similarity_empty(self):
        assert SyntheticOCR.plate_similarity("", "DL01AB1234") == 0.0
        assert SyntheticOCR.plate_similarity("", "") == 0.0

    def test_reproducibility(self):
        ocr1 = SyntheticOCR(error_rate=0.15, seed=123)
        ocr2 = SyntheticOCR(error_rate=0.15, seed=123)
        r1 = ocr1.recognise("DL01AB1234")
        r2 = ocr2.recognise("DL01AB1234")
        assert r1.recognised_plate == r2.recognised_plate
        assert r1.confidence == r2.confidence
