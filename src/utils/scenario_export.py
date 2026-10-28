"""Write a reproducible synthetic simulation run as CSV and JSON artifacts."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import SimulationSettings
from src.association.association_engine import AssociationRecord
from src.evaluation.metrics import EvaluationResult
from src.simulation.detection_generator import Detection
from src.simulation.vehicle_generator import Vehicle
from src.trajectory.trajectory_reconstruction import ReconstructedTrajectory


def export_scenario(
    output_root: Path,
    settings: SimulationSettings,
    vehicles: List[Vehicle],
    detections: List[Detection],
    detection_table: pd.DataFrame,
    association_records: Dict[str, List[AssociationRecord]],
    trajectories_by_method: Dict[str, List[ReconstructedTrajectory]],
    evaluations: Dict[str, EvaluationResult],
    evaluated_detection_count: int,
    tracking_detection_count: Optional[int] = None,
) -> Path:
    """Save one run to a uniquely named folder and return its path."""
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = output_root / f"scenario_seed-{settings.random_seed}_{run_stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    if tracking_detection_count is None:
        tracking_detection_count = len(detections)

    pd.DataFrame([
        {
            "vehicle_id": vehicle.vehicle_id,
            "number_plate": vehicle.number_plate,
            "vehicle_type": vehicle.vehicle_type,
            "colour": vehicle.colour,
            "route": json.dumps(vehicle.route),
            "route_timestamps": json.dumps(vehicle.route_timestamps),
        }
        for vehicle in vehicles
    ]).to_csv(run_dir / "vehicles.csv", index=False)
    detection_table.to_csv(run_dir / "detections.csv", index=False)

    # Store synthetic embeddings separately so the human-readable detection
    # table remains compact. These are simulation features, not model output.
    np.savez_compressed(
        run_dir / "synthetic_embeddings.npz",
        detection_ids=np.asarray([d.detection_id for d in detections]),
        embeddings=np.stack([d.reid_embedding for d in detections]) if detections else np.empty((0, 0)),
    )

    association_rows = []
    for method, records in association_records.items():
        for record in records:
            association_rows.append({
                "method": method,
                "detection_a_id": record.detection_a_id,
                "detection_b_id": record.detection_b_id,
                "final_score": record.final_score,
                "decision": record.decision,
                "component_scores": json.dumps(record.component_scores, sort_keys=True),
                "clm_score": record.clm_result.plausibility_score if record.clm_result else None,
                "camera_path_prior": record.clm_result.transition_probability if record.clm_result else None,
                "explanation": record.explanation,
            })
    pd.DataFrame(association_rows).to_csv(run_dir / "associations.csv", index=False)

    trajectory_rows = []
    for method, trajectories in trajectories_by_method.items():
        for trajectory in trajectories:
            trajectory_rows.append({
                "method": method,
                "trajectory_id": trajectory.trajectory_id,
                "detection_ids": json.dumps(trajectory.detection_ids),
                "camera_sequence": json.dumps(trajectory.camera_sequence),
                "timestamps": json.dumps(trajectory.timestamps),
                "recognised_plates": json.dumps(trajectory.recognised_plates),
                "overall_confidence": trajectory.overall_confidence,
                "segments": json.dumps([asdict(segment) for segment in trajectory.segments]),
                "ground_truth_vehicle_ids_eval_only": json.dumps(trajectory.ground_truth_vehicle_ids),
            })
    pd.DataFrame(trajectory_rows).to_csv(run_dir / "trajectories.csv", index=False)

    metadata = {
        "project": "SmartCity ANPR Trajectory Simulation",
        "synthetic_data_only": True,
        "random_seed": settings.random_seed,
        "settings": asdict(settings),
        "vehicles_generated": len(vehicles),
        "detections_generated": len(detections),
        "detections_evaluated": evaluated_detection_count,
        "evaluation_scope": "The dashboard's evaluation subset; see detections_evaluated.",
        "detections_tracked": tracking_detection_count,
        "trajectory_scope_by_method": {
            "combined": "Full generated run; see detections_tracked.",
            "plate_only": "Evaluation subset; see detections_evaluated.",
            "reid_only": "Evaluation subset; see detections_evaluated.",
        },
        "association_record_scope": "Evaluation subset for each method.",
        "trajectories_by_method": {
            name: len(trajectories) for name, trajectories in trajectories_by_method.items()
        },
        "evaluation_metrics": {name: asdict(value) for name, value in evaluations.items()},
        "notes": [
            "Ground-truth identifiers are included for synthetic evaluation only.",
            "OCR and appearance embeddings are simulated, not trained-model output.",
            "Repeated runs with identical settings and seed generate the same scenario records; export folder timestamps differ.",
        ],
    }
    (run_dir / "scenario.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (run_dir / "README.txt").write_text(
        "Synthetic SmartCity scenario export. Files: vehicles.csv, detections.csv, "
        "associations.csv, trajectories.csv, synthetic_embeddings.npz, scenario.json.\n"
        "Ground-truth fields are for evaluation only. All model-like outputs are simulated.\n",
        encoding="utf-8",
    )
    return run_dir
