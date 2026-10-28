"""
Tests for Trajectory Reconstruction.
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
from src.trajectory.trajectory_reconstruction import (
    TrajectoryReconstructor,
    ReconstructedTrajectory,
)
from config.settings import DEFAULT_CAMERAS


class TestTrajectoryReconstruction:
    """Tests for the TrajectoryReconstructor class."""

    def setup_method(self):
        settings = SimulationSettings(
            num_vehicles=10,
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
        _, self.clusters = engine.associate(self.detections, method="combined")
        self.reconstructor = TrajectoryReconstructor(self.graph)

    def test_reconstruct_returns_trajectories(self):
        trajs = self.reconstructor.reconstruct(self.clusters, self.det_map)
        assert isinstance(trajs, list)
        assert len(trajs) > 0

    def test_trajectory_has_required_fields(self):
        trajs = self.reconstructor.reconstruct(self.clusters, self.det_map)
        t = trajs[0]
        assert isinstance(t, ReconstructedTrajectory)
        assert t.trajectory_id
        assert len(t.detection_ids) > 0
        assert len(t.camera_sequence) > 0
        assert len(t.timestamps) > 0
        assert 0 <= t.overall_confidence <= 1

    def test_timestamps_are_sorted(self):
        trajs = self.reconstructor.reconstruct(self.clusters, self.det_map)
        for t in trajs:
            for i in range(len(t.timestamps) - 1):
                assert t.timestamps[i] <= t.timestamps[i + 1]

    def test_segments_match_camera_sequence(self):
        trajs = self.reconstructor.reconstruct(self.clusters, self.det_map)
        for t in trajs:
            if len(t.camera_sequence) > 1:
                assert len(t.segments) == len(t.camera_sequence) - 1
                for i, seg in enumerate(t.segments):
                    assert seg.from_camera == t.camera_sequence[i]
                    assert seg.to_camera == t.camera_sequence[i + 1]

    def test_segment_types_valid(self):
        trajs = self.reconstructor.reconstruct(self.clusters, self.det_map)
        valid_types = {"observed", "inferred", "uncertain"}
        for t in trajs:
            for seg in t.segments:
                assert seg.segment_type in valid_types

    def test_summary_conversion(self):
        trajs = self.reconstructor.reconstruct(self.clusters, self.det_map)
        summaries = TrajectoryReconstructor.trajectories_to_summary(trajs)
        assert isinstance(summaries, list)
        assert len(summaries) == len(trajs)
        assert "trajectory_id" in summaries[0]
        assert "num_detections" in summaries[0]

    def test_empty_clusters(self):
        trajs = self.reconstructor.reconstruct({}, self.det_map)
        assert trajs == []
