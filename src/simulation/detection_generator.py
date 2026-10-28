"""
Detection Generator Module.

Generates synthetic camera detections from ground-truth vehicles.
Each detection simulates what an ANPR camera would produce, including
configurable imperfections:

- OCR errors and partial plates.
- Missed detections (camera fails to see the vehicle).
- Noisy Re-ID embeddings.
- Variable travel times.
- Vehicles appearing in unexpected order.

Ground-truth vehicle IDs are stored in a *separate* column that is
NEVER used by the association algorithm.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import SimulationSettings
from src.simulation.vehicle_generator import Vehicle
from src.camera_network.camera_graph import CameraGraph
from src.anpr.synthetic_ocr import SyntheticOCR
from src.reid.synthetic_embeddings import SyntheticReID


@dataclass
class Detection:
    """A single camera detection record."""
    detection_id: str
    ground_truth_vehicle_id: str     # For evaluation ONLY, never used in matching
    ground_truth_route_index: int    # Evaluation-only route order, never a matching feature
    camera_id: str
    timestamp: float                 # Epoch seconds (simulation time)
    recognised_plate: str
    ocr_confidence: float
    vehicle_type: str
    vehicle_colour: str
    reid_embedding: np.ndarray
    travel_direction: str
    detection_confidence: float
    is_partial_plate: bool
    plate_hypotheses: List[Tuple[str, float]]
    is_timestamp_order_anomaly: bool = False  # Evaluation-only simulation annotation


class DetectionGenerator:
    """
    Produce synthetic detections from a list of ground-truth vehicles
    and a camera graph.
    """

    DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    def __init__(
        self,
        camera_graph: CameraGraph,
        settings: Optional[SimulationSettings] = None,
    ) -> None:
        self.graph = camera_graph
        self.settings = settings or SimulationSettings()
        self.rng = np.random.default_rng(self.settings.random_seed + 1)

        self.ocr = SyntheticOCR(
            error_rate=self.settings.ocr_error_rate,
            partial_rate=self.settings.ocr_error_rate * 0.3,
            seed=self.settings.random_seed + 2,
        )
        self.reid = SyntheticReID(
            noise_level=self.settings.reid_noise_level,
            embedding_dim=self.settings.embedding_dim,
            seed=self.settings.random_seed + 3,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def generate_detections(
        self, vehicles: List[Vehicle]
    ) -> Tuple[List[Detection], pd.DataFrame]:
        """
        Generate detections for all vehicles.

        Returns:
            (detections_list, detections_dataframe)
            The DataFrame does NOT include embeddings (for display).
            Ground-truth vehicle IDs are in a separate column marked
            '[EVAL ONLY]'.
        """
        detections: List[Detection] = []
        detection_number = 0

        for vehicle in vehicles:
            vehicle_dets = self._generate_vehicle_detections(vehicle)
            # Simulate a misordered camera timestamp while retaining the
            # actual route index separately for evaluation only.
            if (
                len(vehicle_dets) > 1
                and self.rng.random() < self.settings.unexpected_order_rate
            ):
                anomaly_index = int(self.rng.integers(1, len(vehicle_dets)))
                previous_time = vehicle_dets[anomaly_index - 1].timestamp
                vehicle_dets[anomaly_index].timestamp = max(
                    0.0, previous_time - self.rng.uniform(5.0, 90.0)
                )
                vehicle_dets[anomaly_index].is_timestamp_order_anomaly = True
            for detection in vehicle_dets:
                detection_number += 1
                # Stable IDs make a seeded scenario reproducible across runs.
                detection.detection_id = f"DET-{detection_number:07d}"
            detections.extend(vehicle_dets)

        # Sort by timestamp (simulates real-time arrival order)
        detections.sort(key=lambda d: d.timestamp)

        df = self._detections_to_dataframe(detections)
        return detections, df

    # ── Private helpers ─────────────────────────────────────────────────

    def _generate_vehicle_detections(self, vehicle: Vehicle) -> List[Detection]:
        """Generate detections for a single vehicle along its route."""
        dets: List[Detection] = []

        for idx, (cam_id, ts) in enumerate(
            zip(vehicle.route, vehicle.route_timestamps)
        ):
            # Detection failure — camera misses the vehicle
            camera_failure_rate = self.settings.camera_detection_failure_rates.get(
                cam_id, self.settings.detection_failure_rate
            )
            camera_failure_rate = float(np.clip(camera_failure_rate, 0.0, 1.0))
            if self.rng.random() < camera_failure_rate:
                continue

            # How many observations at this camera?
            if self.settings.multi_frame_enabled:
                n_obs = self.rng.integers(1, self.settings.max_observations_per_camera + 1)
            else:
                n_obs = 1

            # Multi-frame OCR
            if n_obs > 1:
                ocr_result = self.ocr.recognise_multi_frame(
                    vehicle.number_plate, num_frames=n_obs
                )
            else:
                ocr_result = self.ocr.recognise(vehicle.number_plate)

            # Noisy Re-ID embedding
            noisy_emb = self.reid.generate_noisy_embedding(vehicle.embedding)

            # Travel direction
            cam_cfg = self.graph.get_camera(cam_id)
            if cam_cfg and cam_cfg.entry_directions:
                direction = self.rng.choice(cam_cfg.entry_directions)
            else:
                direction = self.rng.choice(self.DIRECTIONS)

            # Vehicle type — occasionally misidentify
            if self.rng.random() < 0.05:
                from config.settings import VEHICLE_TYPES
                vtype = self.rng.choice(VEHICLE_TYPES)
            else:
                vtype = vehicle.vehicle_type

            # Vehicle colour — occasionally misidentify
            if self.rng.random() < 0.05:
                from config.settings import VEHICLE_COLOURS
                vcolour = self.rng.choice(VEHICLE_COLOURS)
            else:
                vcolour = vehicle.colour

            # Add small timestamp jitter (±5 seconds)
            jittered_ts = ts + self.rng.normal(0, 2.5)

            # Detection confidence
            det_conf = float(np.clip(
                self.rng.normal(0.85, 0.08), 0.3, 1.0
            ))

            det = Detection(
                detection_id="",  # Assigned deterministically in generate_detections.
                ground_truth_vehicle_id=vehicle.vehicle_id,
                ground_truth_route_index=idx,
                camera_id=cam_id,
                timestamp=jittered_ts,
                recognised_plate=ocr_result.recognised_plate,
                ocr_confidence=ocr_result.confidence,
                vehicle_type=vtype,
                vehicle_colour=vcolour,
                reid_embedding=noisy_emb,
                travel_direction=direction,
                detection_confidence=det_conf,
                is_partial_plate=ocr_result.is_partial,
                plate_hypotheses=ocr_result.hypotheses,
            )
            dets.append(det)

        return dets

    @staticmethod
    def _detections_to_dataframe(detections: List[Detection]) -> pd.DataFrame:
        """Convert detections to a display-friendly DataFrame."""
        rows = []
        for d in detections:
            rows.append({
                "detection_id": d.detection_id,
                "[EVAL ONLY] vehicle_id": d.ground_truth_vehicle_id,
                "[EVAL ONLY] route_index": d.ground_truth_route_index,
                "[EVAL ONLY] timestamp_order_anomaly": d.is_timestamp_order_anomaly,
                "camera_id": d.camera_id,
                "timestamp": d.timestamp,
                "recognised_plate": d.recognised_plate,
                "ocr_confidence": round(d.ocr_confidence, 4),
                "vehicle_type": d.vehicle_type,
                "vehicle_colour": d.vehicle_colour,
                "travel_direction": d.travel_direction,
                "detection_confidence": round(d.detection_confidence, 4),
                "is_partial_plate": d.is_partial_plate,
            })
        return pd.DataFrame(rows)
