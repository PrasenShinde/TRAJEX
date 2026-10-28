"""Reproducible synthetic sensitivity sweeps for OCR and Re-ID noise."""

from dataclasses import replace
from typing import Dict, List

import numpy as np

from config.settings import AssociationWeights, SimulationSettings
from src.association.association_engine import AssociationEngine
from src.evaluation.metrics import EvaluationEngine
from src.simulation.city_generator import CityGenerator
from src.simulation.detection_generator import DetectionGenerator
from src.simulation.vehicle_generator import VehicleGenerator
from src.trajectory.trajectory_reconstruction import TrajectoryReconstructor


SENSITIVITY_LEVELS = (0.0, 0.1, 0.2, 0.3)
METHODS = ("combined", "plate_only", "reid_only")
MAX_FLEET_SIZE = 75
MAX_DETECTIONS_PER_VARIANT = 180


def run_sensitivity_analysis(
    settings: SimulationSettings,
    weights: AssociationWeights,
) -> List[Dict]:
    """Sweep error settings with a shared synthetic fleet and per-condition data.

    All three association methods receive the same detections at each sweep
    level. The underlying generated fleet, routes, and true appearance vectors
    remain fixed across every level.
    """
    fleet_size = min(settings.num_vehicles, MAX_FLEET_SIZE)
    base_settings = replace(settings, num_vehicles=fleet_size)
    camera_graph = CityGenerator(base_settings).build()
    vehicles = VehicleGenerator(camera_graph, base_settings).generate_vehicles()
    association_engine = AssociationEngine(camera_graph, weights)
    reconstructor = TrajectoryReconstructor(camera_graph)
    evaluator = EvaluationEngine()

    rows: List[Dict] = []
    sweeps = (
        ("OCR error rate", "ocr_error_rate"),
        ("Re-ID noise level", "reid_noise_level"),
    )
    for label, setting_name in sweeps:
        for level in SENSITIVITY_LEVELS:
            variant_settings = replace(base_settings, **{setting_name: level})
            detections, _ = DetectionGenerator(
                camera_graph, variant_settings
            ).generate_detections(vehicles)
            if len(detections) > MAX_DETECTIONS_PER_VARIANT:
                sample_indices = np.linspace(
                    0, len(detections) - 1,
                    MAX_DETECTIONS_PER_VARIANT,
                    dtype=int,
                )
                evaluated_detections = [detections[index] for index in sample_indices]
            else:
                evaluated_detections = detections
            det_map = {detection.detection_id: detection for detection in detections}

            for method in METHODS:
                _, clusters = association_engine.associate(evaluated_detections, method)
                trajectories = reconstructor.reconstruct(clusters, det_map)
                result = evaluator.evaluate_trajectories(
                    trajectories, evaluated_detections, method
                )
                rows.append({
                    "Parameter": label,
                    "Level": level,
                    "Method": method,
                    "Precision": result.precision,
                    "Recall": result.recall,
                    "F1": result.f1_score,
                    "Trajectories": result.total_reconstructed_trajectories,
                    "Detections evaluated": len(evaluated_detections),
                })
    return rows
