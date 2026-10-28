"""
Cross-Camera Vehicle Association Engine.

Combines plate similarity, Re-ID similarity, vehicle-attribute consistency,
timestamp scoring, and Camera Link Model (CLM) plausibility into a single
weighted score for every candidate detection pair.

Supports three matching strategies:
  1. plate_only   — uses only plate similarity.
  2. reid_only    — uses only Re-ID cosine similarity.
  3. combined     — uses all evidence sources with configurable weights.

The engine uses a maximum-weight bipartite assignment to choose a globally
consistent set of forward-time predecessor/successor links. This creates a
path cover in which each detection has at most one predecessor and successor.

Every accepted, rejected, or uncertain association is logged with a
human-readable explanation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import linear_sum_assignment

from config.settings import AssociationWeights
from src.simulation.detection_generator import Detection
from src.association.similarity import SimilarityScorer
from src.camera_network.camera_graph import CameraGraph
from src.camera_network.camera_link_model import CameraLinkModel, CLMResult


@dataclass
class AssociationRecord:
    """Record of a single association decision."""
    detection_a_id: str
    detection_b_id: str
    component_scores: Dict[str, float]
    clm_result: Optional[CLMResult]
    final_score: float
    decision: str               # "accepted", "rejected", "uncertain"
    explanation: str
    method: str                 # "plate_only", "reid_only", "combined"


class AssociationEngine:
    """
    Cross-camera vehicle association engine.

    Usage:
        engine = AssociationEngine(camera_graph)
        records, clusters = engine.associate(detections, method="combined")
    """

    def __init__(
        self,
        camera_graph: CameraGraph,
        weights: Optional[AssociationWeights] = None,
    ) -> None:
        self.graph = camera_graph
        self.clm = CameraLinkModel(camera_graph)
        self.weights = weights or AssociationWeights()
        self.scorer = SimilarityScorer()

    # ── Public API ──────────────────────────────────────────────────────

    def associate(
        self,
        detections: List[Detection],
        method: str = "combined",
        record_all_candidates: bool = True,
    ) -> Tuple[List[AssociationRecord], Dict[str, List[str]]]:
        """
        Associate detections into vehicle clusters.

        Args:
            detections: List of Detection objects sorted by timestamp.
            method: One of "plate_only", "reid_only", "combined".

        Returns:
            (association_records, clusters)
            clusters: dict mapping cluster_id → list of detection IDs.
        """
        if method not in {"combined", "plate_only", "reid_only"}:
            raise ValueError(
                "method must be one of: 'combined', 'plate_only', or 'reid_only'."
            )
        camera_ids = set(self.graph.get_all_camera_ids())
        seen_detection_ids = set()
        embedding_shape = None
        for detection in detections:
            if not isinstance(detection.detection_id, str) or not detection.detection_id.strip():
                raise ValueError("Every detection must have a non-empty detection_id.")
            if detection.detection_id in seen_detection_ids:
                raise ValueError(f"Duplicate detection_id: {detection.detection_id}")
            seen_detection_ids.add(detection.detection_id)
            if detection.camera_id not in camera_ids:
                raise ValueError(
                    f"Detection {detection.detection_id} references unknown camera "
                    f"{detection.camera_id!r}."
                )
            if isinstance(detection.timestamp, bool) or not isinstance(
                detection.timestamp, (int, float, np.integer, np.floating)
            ):
                raise ValueError(f"Detection {detection.detection_id} has an invalid timestamp.")
            try:
                timestamp = float(detection.timestamp)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Detection {detection.detection_id} has an invalid timestamp."
                ) from exc
            if not np.isfinite(timestamp):
                raise ValueError(f"Detection {detection.detection_id} has a non-finite timestamp.")
            for field_name in ("ocr_confidence", "detection_confidence"):
                raw_score = getattr(detection, field_name)
                if isinstance(raw_score, bool) or not isinstance(
                    raw_score, (int, float, np.integer, np.floating)
                ):
                    raise ValueError(
                        f"Detection {detection.detection_id} has invalid {field_name}."
                    )
                try:
                    score = float(raw_score)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Detection {detection.detection_id} has invalid {field_name}."
                    ) from exc
                if not np.isfinite(score) or not 0.0 <= score <= 1.0:
                    raise ValueError(
                        f"Detection {detection.detection_id} has invalid {field_name}; "
                        "expected a finite value from 0 to 1."
                    )
            try:
                embedding = np.asarray(detection.reid_embedding, dtype=float)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Detection {detection.detection_id} has a non-numeric Re-ID embedding."
                ) from exc
            if embedding.ndim != 1 or embedding.size == 0 or not np.all(np.isfinite(embedding)):
                raise ValueError(
                    f"Detection {detection.detection_id} has an invalid Re-ID embedding; "
                    "expected a non-empty finite vector."
                )
            if embedding_shape is None:
                embedding_shape = embedding.shape
            elif embedding.shape != embedding_shape:
                raise ValueError("All detections in one association run must use embeddings of the same size.")

        detections = sorted(detections, key=lambda detection: detection.timestamp)
        n = len(detections)
        if n == 0:
            return [], {}

        # Build lookup
        det_map: Dict[str, Detection] = {d.detection_id: d for d in detections}
        det_ids = [d.detection_id for d in detections]

        # ── Step 1: Score all candidate pairs ───────────────────────────
        records: List[AssociationRecord] = []
        accepted_edges: List[Tuple[int, int, float, AssociationRecord]] = []
        record_by_pair: Dict[Tuple[str, str], AssociationRecord] = {}
        # Bipartite candidate components let assignment matrices stay small:
        # each detection has separate predecessor and successor vertices.
        candidate_parent = list(range(2 * n))

        def candidate_find(node: int) -> int:
            while candidate_parent[node] != node:
                candidate_parent[node] = candidate_parent[candidate_parent[node]]
                node = candidate_parent[node]
            return node

        def candidate_union(left_node: int, right_node: int) -> None:
            left_root = candidate_find(left_node)
            right_root = candidate_find(right_node)
            if left_root != right_root:
                candidate_parent[left_root] = right_root
        timestamps = np.fromiter(
            (detection.timestamp for detection in detections), dtype=float, count=n
        )
        camera_indices = {}
        camera_timestamps = {}
        if not record_all_candidates:
            for camera_id in sorted(camera_ids):
                indices = np.asarray([
                    index for index, detection in enumerate(detections)
                    if detection.camera_id == camera_id
                ], dtype=int)
                camera_indices[camera_id] = indices
                camera_timestamps[camera_id] = timestamps[indices]

        for i in range(n):
            det_a = detections[i]
            if record_all_candidates:
                # Keep the complete candidate audit trail for evaluation runs.
                stop = int(np.searchsorted(
                    timestamps,
                    det_a.timestamp + self.weights.max_time_gap_seconds,
                    side="right",
                ))
                candidate_indices = range(i + 1, stop)
            else:
                # For full-run tracking, index by camera and the conservative
                # CLM time interval so unrelated time-window pairs are skipped.
                candidate_indices = []
                for target_camera in sorted(camera_ids):
                    bounds = self.clm.candidate_time_bounds(
                        det_a.camera_id,
                        target_camera,
                        self.weights.max_time_gap_seconds,
                    )
                    if bounds is None:
                        continue
                    target_times = camera_timestamps[target_camera]
                    target_ids = camera_indices[target_camera]
                    begin = int(np.searchsorted(
                        target_times, det_a.timestamp + bounds[0], side="left"
                    ))
                    end = int(np.searchsorted(
                        target_times, det_a.timestamp + bounds[1], side="right"
                    ))
                    candidate_indices.extend(target_ids[begin:end].tolist())
                candidate_indices = sorted(j for j in candidate_indices if j > i)

            for j in candidate_indices:
                det_a = detections[i]
                det_b = detections[j]

                # Hard constraint: same camera and very close in time
                # (likely the same observation, not a transition)
                if det_a.camera_id == det_b.camera_id:
                    if abs(det_a.timestamp - det_b.timestamp) < 10:
                        continue

                # Hard constraint: max time gap
                elapsed = det_b.timestamp - det_a.timestamp
                if elapsed <= 0:
                    continue
                record = self._score_pair(det_a, det_b, method)
                if record.decision == "accepted":
                    accepted_edges.append((i, j, record.final_score, record))
                    candidate_union(i, n + j)
                    record_by_pair[(det_a.detection_id, det_b.detection_id)] = record
                if record_all_candidates or record.decision == "accepted":
                    records.append(record)

        # ── Step 2: Global one-to-one path assignment ────────────────────
        selected_pairs = set()
        edges_by_component: Dict[int, List[Tuple[int, int, float]]] = {}
        left_by_component: Dict[int, set] = {}
        right_by_component: Dict[int, set] = {}
        for i, j, score, _ in accepted_edges:
            root = candidate_find(i)
            edges_by_component.setdefault(root, []).append((i, j, score))
            left_by_component.setdefault(root, set()).add(i)
            right_by_component.setdefault(root, set()).add(j)

        for root, edges in edges_by_component.items():
            left_nodes = sorted(left_by_component[root])
            right_nodes = sorted(right_by_component[root])
            left_index = {node: index for index, node in enumerate(left_nodes)}
            right_index = {node: index for index, node in enumerate(right_nodes)}
            component_scores = np.zeros((len(left_nodes), len(right_nodes)), dtype=float)
            for i, j, score in edges:
                component_scores[left_index[i], right_index[j]] = score
            rows, columns = linear_sum_assignment(component_scores, maximize=True)
            for row, column in zip(rows, columns):
                if component_scores[row, column] > 0:
                    detection_a_id = detections[left_nodes[row]].detection_id
                    detection_b_id = detections[right_nodes[column]].detection_id
                    selected_pairs.add((detection_a_id, detection_b_id))

        for pair, record in record_by_pair.items():
            if record.decision == "accepted" and pair not in selected_pairs:
                record.decision = "uncertain"
                record.explanation += (
                    " | Not selected by the global assignment; another link "
                    "provided a better one-to-one path cover."
                )

        # Union-Find for clustering
        parent: Dict[str, str] = {d.detection_id: d.detection_id for d in detections}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        for detection_a_id, detection_b_id in selected_pairs:
            union(detection_a_id, detection_b_id)

        # ── Step 3: Build cluster dict ──────────────────────────────────
        clusters: Dict[str, List[str]] = {}
        for det_id in det_ids:
            root = find(det_id)
            cluster_key = f"TRAJ-{root}"
            if cluster_key not in clusters:
                clusters[cluster_key] = []
            clusters[cluster_key].append(det_id)

        return records, clusters

    # ── Scoring ─────────────────────────────────────────────────────────

    def _score_pair(
        self,
        det_a: Detection,
        det_b: Detection,
        method: str,
    ) -> AssociationRecord:
        """Score a single candidate pair."""
        # Component scores
        components = self.scorer.compute_all(
            det_a, det_b, self.weights.max_time_gap_seconds
        )

        # CLM evaluation
        elapsed = det_b.timestamp - det_a.timestamp
        clm_result = self.clm.evaluate(
            det_a.camera_id, det_b.camera_id,
            elapsed,
            det_a.travel_direction, det_b.travel_direction,
        )
        components["clm_plausibility"] = clm_result.plausibility_score

        # ── Compute final score based on method ─────────────────────────
        if method == "plate_only":
            final_score = components["plate_similarity"]
            has_active_combined_weights = True
            explanation_parts = [
                f"Plate sim: {components['plate_similarity']:.3f}",
            ]
        elif method == "reid_only":
            final_score = components["reid_similarity"]
            has_active_combined_weights = True
            explanation_parts = [
                f"ReID sim: {components['reid_similarity']:.3f}",
            ]
        else:  # combined
            w = self.weights
            raw_weights = {
                "plate_similarity": max(0.0, float(w.plate_similarity)),
                "reid_similarity": max(0.0, float(w.reid_similarity)),
                "vehicle_type_match": max(0.0, float(w.vehicle_type_match)),
                "colour_match": max(0.0, float(w.colour_match)),
                "clm_plausibility": max(0.0, float(w.clm_plausibility)),
                "timestamp_score": max(0.0, float(w.timestamp_score)),
                "direction_match": max(0.0, float(w.direction_match)),
            }
            weight_total = sum(raw_weights.values())
            has_active_combined_weights = weight_total > 0.0
            normalized_weights = (
                {key: value / weight_total for key, value in raw_weights.items()}
                if has_active_combined_weights else
                {key: 0.0 for key in raw_weights}
            )
            final_score = sum(
                normalized_weights[key] * components[key]
                for key in normalized_weights
            )
            final_score = float(np.clip(final_score, 0.0, 1.0))
            explanation_parts = [
                f"Plate: {components['plate_similarity']:.3f}×{normalized_weights['plate_similarity']:.3f}",
                f"ReID: {components['reid_similarity']:.3f}×{normalized_weights['reid_similarity']:.3f}",
                f"Type: {components['vehicle_type_match']:.1f}×{normalized_weights['vehicle_type_match']:.3f}",
                f"Colour: {components['colour_match']:.1f}×{normalized_weights['colour_match']:.3f}",
                f"CLM: {components['clm_plausibility']:.3f}×{normalized_weights['clm_plausibility']:.3f}",
                f"Time: {components['timestamp_score']:.3f}×{normalized_weights['timestamp_score']:.3f}",
                f"Dir: {components['direction_match']:.2f}×{normalized_weights['direction_match']:.3f}",
            ]

        # ── Hard-constraint rejection ───────────────────────────────────
        decision = "uncertain"
        reasons = []

        if method == "combined" and not has_active_combined_weights:
            decision = "rejected"
            reasons.append("All combined evidence weights are zero; no score can support a match.")

        if components["plate_similarity"] < self.weights.min_plate_similarity:
            if method in ("plate_only", "combined"):
                decision = "rejected"
                reasons.append(
                    f"Plate similarity {components['plate_similarity']:.3f} "
                    f"below threshold {self.weights.min_plate_similarity}"
                )

        if clm_result.plausibility_score <= 0.05:
            decision = "rejected"
            reasons.append(f"CLM score near zero: {clm_result.explanation}")

        if components["timestamp_score"] == 0.0:
            decision = "rejected"
            reasons.append("Temporal gap exceeds maximum or wrong order")

        if decision != "rejected":
            if final_score >= self.weights.min_association_score:
                decision = "accepted"
                reasons.append(f"Score {final_score:.3f} ≥ threshold {self.weights.min_association_score}")
            else:
                decision = "rejected"
                reasons.append(
                    f"Score {final_score:.3f} < threshold {self.weights.min_association_score}"
                )

        explanation = " | ".join(explanation_parts) + " → " + "; ".join(reasons)

        return AssociationRecord(
            detection_a_id=det_a.detection_id,
            detection_b_id=det_b.detection_id,
            component_scores=components,
            clm_result=clm_result,
            final_score=round(final_score, 4),
            decision=decision,
            explanation=explanation,
            method=method,
        )
