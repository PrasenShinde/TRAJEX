"""
Trajectory Reconstruction Module.

Reconstructs probable vehicle trajectories from clusters of associated
detections.  Distinguishes between observed sightings, inferred
transitions, and uncertain segments.

An inferred route is NEVER represented as confirmed vehicle movement.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from src.simulation.detection_generator import Detection
from src.camera_network.camera_graph import CameraGraph


@dataclass
class TrajectorySegment:
    """A single segment of a trajectory (between two consecutive cameras)."""
    from_camera: str
    to_camera: str
    from_timestamp: float
    to_timestamp: float
    elapsed_seconds: float
    segment_type: str            # "observed", "inferred", "uncertain"
    confidence: float
    explanation: str


@dataclass
class ReconstructedTrajectory:
    """A fully reconstructed vehicle trajectory."""
    trajectory_id: str
    detection_ids: List[str]
    camera_sequence: List[str]
    timestamps: List[float]
    recognised_plates: List[str]
    segments: List[TrajectorySegment]
    overall_confidence: float
    num_observed: int
    num_inferred: int
    num_uncertain: int
    ground_truth_vehicle_ids: List[str]  # For evaluation only


class TrajectoryReconstructor:
    """
    Reconstruct trajectories from detection clusters produced by the
    association engine.
    """

    def __init__(self, camera_graph: CameraGraph) -> None:
        self.graph = camera_graph

    def reconstruct(
        self,
        clusters: Dict[str, List[str]],
        det_map: Dict[str, Detection],
    ) -> List[ReconstructedTrajectory]:
        """
        Build trajectories from association clusters.

        Args:
            clusters: Dict mapping cluster_id → list of detection IDs.
            det_map: Dict mapping detection_id → Detection object.

        Returns:
            List of ReconstructedTrajectory objects.
        """
        trajectories: List[ReconstructedTrajectory] = []

        for cluster_id, det_ids in clusters.items():
            # Retrieve detections and sort by timestamp
            dets = [det_map[did] for did in det_ids if did in det_map]
            if not dets:
                continue
            dets.sort(key=lambda d: d.timestamp)

            camera_seq = [d.camera_id for d in dets]
            timestamps = [d.timestamp for d in dets]
            plates = [d.recognised_plate for d in dets]
            gt_vids = list(set(d.ground_truth_vehicle_id for d in dets))

            # Build segments between consecutive sightings
            segments = []
            for i in range(len(dets) - 1):
                seg = self._build_segment(dets[i], dets[i + 1])
                segments.append(seg)

            # Calculate overall confidence
            num_observed = sum(1 for s in segments if s.segment_type == "observed")
            num_inferred = sum(1 for s in segments if s.segment_type == "inferred")
            num_uncertain = sum(1 for s in segments if s.segment_type == "uncertain")

            if segments:
                overall_conf = float(np.mean([s.confidence for s in segments]))
            else:
                overall_conf = 0.5 if len(dets) == 1 else 0.0

            traj = ReconstructedTrajectory(
                trajectory_id=cluster_id,
                detection_ids=[d.detection_id for d in dets],
                camera_sequence=camera_seq,
                timestamps=timestamps,
                recognised_plates=plates,
                segments=segments,
                overall_confidence=round(overall_conf, 4),
                num_observed=num_observed + len(dets),  # each detection is an observation
                num_inferred=num_inferred,
                num_uncertain=num_uncertain,
                ground_truth_vehicle_ids=gt_vids,
            )
            trajectories.append(traj)

        # Sort by number of detections (descending)
        trajectories.sort(key=lambda t: len(t.detection_ids), reverse=True)
        return trajectories

    def _build_segment(
        self, det_from: Detection, det_to: Detection
    ) -> TrajectorySegment:
        """Build a segment between two consecutive detections."""
        elapsed = det_to.timestamp - det_from.timestamp
        from_cam = det_from.camera_id
        to_cam = det_to.camera_id

        # Determine segment type
        if from_cam == to_cam:
            seg_type = "observed"
            confidence = 0.9
            expl = f"Re-observation at {from_cam}."
        elif self.graph.are_directly_connected(from_cam, to_cam):
            dist = self.graph.get_travel_time_distribution(from_cam, to_cam)
            if dist:
                mean_tt, std_tt = dist
                z = abs(elapsed - mean_tt) / max(std_tt, 1.0)
                if z < 2.0:
                    seg_type = "inferred"
                    confidence = float(np.clip(1.0 - z * 0.2, 0.3, 1.0))
                    expl = (
                        f"Inferred direct graph connection {from_cam}→{to_cam}; "
                        "the road route is not observed. "
                        f"Elapsed {elapsed:.0f}s vs expected {mean_tt:.0f}±{std_tt:.0f}s."
                    )
                else:
                    seg_type = "uncertain"
                    confidence = float(np.clip(0.5 - (z - 2) * 0.1, 0.1, 0.5))
                    expl = (
                        f"Direct connection but unusual timing: "
                        f"{elapsed:.0f}s vs {mean_tt:.0f}±{std_tt:.0f}s (z={z:.1f})."
                    )
            else:
                seg_type = "inferred"
                confidence = 0.7
                expl = (
                    f"Inferred direct graph connection {from_cam}→{to_cam}; "
                    "the road route is not observed and timing data is unavailable."
                )
        else:
            # Check if there is any path
            path = self.graph.shortest_path(from_cam, to_cam)
            if path:
                seg_type = "inferred"
                hops = len(path) - 1
                confidence = float(np.clip(0.6 - hops * 0.1, 0.1, 0.6))
                missing_cams = path[1:-1]
                expl = (
                    f"Inferred route {from_cam}→{to_cam} via {hops} hops. "
                    f"Missing cameras: {missing_cams}. "
                    f"This is NOT a confirmed path."
                )
            else:
                seg_type = "uncertain"
                confidence = 0.1
                expl = (
                    f"No known path from {from_cam} to {to_cam}. "
                    f"Transition is uncertain — may indicate an "
                    f"unmodelled road or a misassociation."
                )

        return TrajectorySegment(
            from_camera=from_cam,
            to_camera=to_cam,
            from_timestamp=det_from.timestamp,
            to_timestamp=det_to.timestamp,
            elapsed_seconds=elapsed,
            segment_type=seg_type,
            confidence=round(confidence, 4),
            explanation=expl,
        )

    @staticmethod
    def trajectories_to_summary(
        trajectories: List[ReconstructedTrajectory],
    ) -> List[Dict]:
        """Convert trajectories to a list of summary dicts for display."""
        summaries = []
        for t in trajectories:
            most_common_plate = max(
                set(t.recognised_plates),
                key=t.recognised_plates.count,
            ) if t.recognised_plates else "N/A"

            summaries.append({
                "trajectory_id": t.trajectory_id,
                "num_detections": len(t.detection_ids),
                "camera_sequence": " → ".join(t.camera_sequence),
                "most_common_plate": most_common_plate,
                "overall_confidence": t.overall_confidence,
                "num_inferred_segments": t.num_inferred,
                "num_uncertain_segments": t.num_uncertain,
                "duration_seconds": round(
                    t.timestamps[-1] - t.timestamps[0], 1
                ) if len(t.timestamps) > 1 else 0.0,
                "ground_truth_ids": ", ".join(t.ground_truth_vehicle_ids),
            })
        return summaries
