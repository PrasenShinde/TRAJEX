"""
Tests for the Cross-Camera Association Engine.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np
from config.settings import SimulationSettings
from src.camera_network.camera_graph import CameraGraph
from src.simulation.vehicle_generator import VehicleGenerator
from src.simulation.detection_generator import DetectionGenerator
from src.association.association_engine import AssociationEngine
from config.settings import DEFAULT_CAMERAS


class TestAssociationEngine:
    """Tests for the AssociationEngine class."""

    def setup_method(self):
        settings = SimulationSettings(
            num_vehicles=10,
            random_seed=42,
            ocr_error_rate=0.05,
            detection_failure_rate=0.0,
        )
        self.graph = CameraGraph(DEFAULT_CAMERAS)
        vgen = VehicleGenerator(self.graph, settings)
        self.vehicles = vgen.generate_vehicles()
        dgen = DetectionGenerator(self.graph, settings)
        self.detections, _ = dgen.generate_detections(self.vehicles)
        self.engine = AssociationEngine(self.graph)

    def test_association_returns_records_and_clusters(self):
        records, clusters = self.engine.associate(self.detections, method="combined")
        assert isinstance(records, list)
        assert isinstance(clusters, dict)

    def test_clusters_contain_all_detections(self):
        _, clusters = self.engine.associate(self.detections, method="combined")
        all_det_ids = set()
        for det_ids in clusters.values():
            all_det_ids.update(det_ids)
        for d in self.detections:
            assert d.detection_id in all_det_ids

    def test_plate_only_method(self):
        records, clusters = self.engine.associate(self.detections, method="plate_only")
        for r in records:
            assert r.method == "plate_only"

    def test_reid_only_method(self):
        records, clusters = self.engine.associate(self.detections, method="reid_only")
        for r in records:
            assert r.method == "reid_only"

    def test_combined_method(self):
        records, clusters = self.engine.associate(self.detections, method="combined")
        for r in records:
            assert r.method == "combined"

    def test_accepted_records_have_valid_scores(self):
        records, _ = self.engine.associate(self.detections, method="combined")
        for r in records:
            if r.decision == "accepted":
                assert r.final_score >= 0
                assert r.final_score <= 1.5  # Weighted sum can slightly exceed 1

    def test_no_self_association(self):
        records, _ = self.engine.associate(self.detections, method="combined")
        for r in records:
            assert r.detection_a_id != r.detection_b_id

    def test_empty_detections(self):
        records, clusters = self.engine.associate([], method="combined")
        assert records == []
        assert clusters == {}

    def test_explanation_not_empty(self):
        records, _ = self.engine.associate(self.detections, method="combined")
        for r in records[:20]:
            assert isinstance(r.explanation, str)
            assert len(r.explanation) > 0
