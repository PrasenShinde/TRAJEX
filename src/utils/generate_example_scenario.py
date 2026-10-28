"""Generate a small, reproducible example scenario without launching Streamlit."""

from pathlib import Path

from config.settings import SimulationSettings
from src.association.association_engine import AssociationEngine
from src.evaluation.metrics import EvaluationEngine
from src.simulation.city_generator import CityGenerator
from src.simulation.detection_generator import DetectionGenerator
from src.simulation.vehicle_generator import VehicleGenerator
from src.trajectory.trajectory_reconstruction import TrajectoryReconstructor
from src.utils.scenario_export import export_scenario


def generate_example_scenario() -> Path:
    """Create the checked-in 24-vehicle example and return its export folder."""
    project_root = Path(__file__).resolve().parents[2]
    settings = SimulationSettings(
        num_vehicles=24,
        num_cameras=8,
        simulation_duration_hours=3.0,
        random_seed=2026,
        ocr_error_rate=0.12,
        detection_failure_rate=0.08,
        camera_detection_failure_rates={"CAM-03": 0.22},
        reid_noise_level=0.15,
        similar_appearance_rate=0.18,
        unexpected_order_rate=0.12,
        multi_frame_enabled=True,
        max_observations_per_camera=3,
    )
    camera_graph = CityGenerator(settings).build()
    vehicles = VehicleGenerator(camera_graph, settings).generate_vehicles()
    detections, detection_table = DetectionGenerator(
        camera_graph, settings
    ).generate_detections(vehicles)
    detection_map = {detection.detection_id: detection for detection in detections}

    engine = AssociationEngine(camera_graph)
    reconstructor = TrajectoryReconstructor(camera_graph)
    evaluator = EvaluationEngine()
    records_by_method = {}
    trajectories_by_method = {}
    evaluations = {}
    for method in ("combined", "plate_only", "reid_only"):
        records, clusters = engine.associate(detections, method=method)
        trajectories = reconstructor.reconstruct(clusters, detection_map)
        records_by_method[method] = records
        trajectories_by_method[method] = trajectories
        evaluations[method] = evaluator.evaluate_trajectories(
            trajectories, detections, method=method
        )

    return export_scenario(
        project_root / "data" / "generated",
        settings,
        vehicles,
        detections,
        detection_table,
        records_by_method,
        trajectories_by_method,
        evaluations,
        len(detections),
    )


if __name__ == "__main__":
    print(generate_example_scenario())
