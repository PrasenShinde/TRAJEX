"""
Tests for the Evaluation Metrics module.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from config.settings import SimulationSettings
from src.camera_network.camera_graph import CameraGraph
from src.simulation.vehicle_generator import VehicleGenerator
from src.simulation.detection_generator import DetectionGenerator
from src.association.association_engine import AssociationEngine
from src.trajectory.trajectory_reconstruction import TrajectoryReconstructor
from src.evaluation.metrics import EvaluationEngine, EvaluationResult
from config.settings import DEFAULT_CAMERAS


class TestEvaluation:
    """Tests for the EvaluationEngine class."""

    def setup_method(self):
        settings = SimulationSettings(
            num_vehicles=15,
            random_seed=42,
            ocr_error_rate=0.05,
            detection_failure_rate=0.0,
        )
        self.graph = CameraGraph(DEFAULT_CAMERAS)
        vgen = VehicleGenerator(self.graph, settings)
        vehicles = vgen.generate_vehicles()
        dgen = DetectionGenerator(self.graph, settings)
        self.detections, _ = dgen.generate_detections(vehicles)
        self.det_map = {d.detection_id: d for d in self.detections}

        engine = AssociationEngine(self.graph)
        self.records, self.clusters = engine.associate(
            self.detections, method="combined"
        )
        reconstructor = TrajectoryReconstructor(self.graph)
        self.trajectories = reconstructor.reconstruct(self.clusters, self.det_map)

        self.evaluator = EvaluationEngine()

    def test_evaluate_associations_returns_result(self):
        result = self.evaluator.evaluate_associations(
            self.records, self.detections, method="combined"
        )
        assert isinstance(result, EvaluationResult)

    def test_precision_recall_in_range(self):
        result = self.evaluator.evaluate_associations(
            self.records, self.detections, method="combined"
        )
        assert 0 <= result.precision <= 1
        assert 0 <= result.recall <= 1
        assert 0 <= result.f1_score <= 1

    def test_evaluate_trajectories(self):
        result = self.evaluator.evaluate_trajectories(
            self.trajectories, self.detections, method="combined"
        )
        assert isinstance(result, EvaluationResult)
        assert 0 <= result.trajectory_completeness <= 1

    def test_compare_methods(self):
        results = {}
        for method in ["combined", "plate_only", "reid_only"]:
            results[method] = self.evaluator.evaluate_associations(
                self.records, self.detections, method=method
            )
        comparison = self.evaluator.compare_methods(results)
        assert isinstance(comparison, list)
        assert len(comparison) == 3

    def test_zero_division_handled(self):
        """Empty records should not crash."""
        result = self.evaluator.evaluate_associations([], self.detections, method="combined")
        assert result.precision == 0.0
        assert result.recall == 0.0

    def test_correct_plus_incorrect_matches_total(self):
        result = self.evaluator.evaluate_associations(
            self.records, self.detections, method="combined"
        )
        total_accepted = sum(1 for r in self.records if r.decision == "accepted" and r.method == "combined")
        assert result.correct_associations + result.incorrect_associations == total_accepted
