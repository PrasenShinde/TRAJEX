"""
Tests for the Camera Link Model.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.camera_network.camera_graph import CameraGraph
from src.camera_network.camera_link_model import CameraLinkModel, CLMResult
from config.settings import DEFAULT_CAMERAS


class TestCameraLinkModel:
    """Tests for the CameraLinkModel class."""

    def setup_method(self):
        self.graph = CameraGraph(DEFAULT_CAMERAS)
        self.clm = CameraLinkModel(self.graph)

    def test_direct_connection_plausible(self):
        """CAM-01 → CAM-02 with ~300s travel should score well."""
        result = self.clm.evaluate("CAM-01", "CAM-02", 300.0)
        assert isinstance(result, CLMResult)
        assert result.plausibility_score > 0.5
        assert result.is_direct_connection is True
        assert result.shortest_hops == 1

    def test_direct_connection_too_fast(self):
        """Impossibly fast travel should be penalised."""
        result = self.clm.evaluate("CAM-01", "CAM-02", 30.0)
        assert result.plausibility_score < 0.5

    def test_direct_connection_too_slow(self):
        """Very slow travel should lower the score."""
        result = self.clm.evaluate("CAM-01", "CAM-02", 3000.0)
        assert result.plausibility_score < 0.3

    def test_no_connection(self):
        """CAM-08 has no outgoing edges — reverse path doesn't exist."""
        result = self.clm.evaluate("CAM-08", "CAM-01", 300.0)
        assert result.plausibility_score < 0.1
        assert result.shortest_hops is None

    def test_negative_elapsed(self):
        """Negative elapsed time should give score 0."""
        result = self.clm.evaluate("CAM-01", "CAM-02", -100.0)
        assert result.plausibility_score == 0.0

    def test_same_camera_short(self):
        """Same camera with short gap should be plausible."""
        result = self.clm.evaluate("CAM-04", "CAM-04", 5.0)
        assert result.plausibility_score > 0.5

    def test_multi_hop_path(self):
        """CAM-01 → CAM-07 (multi-hop) should be possible but discounted."""
        result = self.clm.evaluate("CAM-01", "CAM-07", 800.0)
        assert result.plausibility_score > 0.0
        assert result.shortest_hops is not None
        assert result.shortest_hops >= 2

    def test_explanation_is_string(self):
        result = self.clm.evaluate("CAM-01", "CAM-02", 300.0)
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0

    def test_all_cameras_reachable_from_01(self):
        """From CAM-01 most cameras should be reachable."""
        for cam_id in ["CAM-02", "CAM-04", "CAM-05", "CAM-07", "CAM-08"]:
            result = self.clm.evaluate("CAM-01", cam_id, 600.0)
            assert result.shortest_hops is not None, f"CAM-01 → {cam_id} unreachable"
