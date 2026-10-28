"""
Evaluation Metrics Module.

Compares reconstructed associations and trajectories against synthetic
ground-truth identities.  Calculates precision, recall, F1-score,
false-match rate, missed-association rate, and trajectory completeness.

IMPORTANT: These metrics are computed against *synthetic* ground truth.
They should NOT be presented as real-world performance guarantees.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from src.simulation.detection_generator import Detection
from src.association.association_engine import AssociationRecord
from src.trajectory.trajectory_reconstruction import ReconstructedTrajectory


@dataclass
class EvaluationResult:
    """Full evaluation result for a single matching method."""
    method: str
    precision: float
    recall: float
    f1_score: float
    false_match_rate: float
    missed_association_rate: float
    total_detections: int
    total_ground_truth_vehicles: int
    total_reconstructed_trajectories: int
    correct_associations: int
    incorrect_associations: int
    missed_associations: int
    unmatched_detections: int
    trajectory_completeness: float      # Fraction of GT transitions recovered
    correct_transitions_pct: float      # % of reconstructed transitions that are correct
    per_vehicle_details: List[Dict]     # Optional per-vehicle breakdown


class EvaluationEngine:
    """
    Evaluate association and trajectory reconstruction quality
    against ground-truth vehicle identities.
    """

    def evaluate_associations(
        self,
        records: List[AssociationRecord],
        detections: List[Detection],
        method: str = "combined",
    ) -> EvaluationResult:
        """
        Evaluate pairwise association decisions.

        A pair is correct when it matches a consecutive ground-truth link in
        timestamp order. This makes edge precision/recall comparable to the
        links reported by trajectory reconstruction.
        """
        det_map = {d.detection_id: d for d in detections}

        accepted = [r for r in records if r.decision == "accepted" and r.method == method]

        from collections import Counter, defaultdict
        by_vehicle: Dict[str, List[Detection]] = defaultdict(list)
        for detection in detections:
            by_vehicle[detection.ground_truth_vehicle_id].append(detection)
        gt_links = set()
        for vehicle_dets in by_vehicle.values():
            vehicle_dets.sort(key=lambda detection: (
                detection.ground_truth_route_index, detection.timestamp
            ))
            gt_links.update(
                (vehicle_dets[i].detection_id, vehicle_dets[i + 1].detection_id)
                for i in range(len(vehicle_dets) - 1)
            )

        predicted_links = {
            (record.detection_a_id, record.detection_b_id)
            for record in accepted
            if record.detection_a_id in det_map and record.detection_b_id in det_map
        }
        tp = len(predicted_links & gt_links)
        fp = len(predicted_links - gt_links)
        fn = len(gt_links - predicted_links)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        false_match_rate = fp / (tp + fp) if (tp + fp) else 0.0
        missed_rate = fn / (tp + fn) if (tp + fn) else 0.0

        # Unmatched: detections that appear in no accepted association
        matched_ids = set()
        for detection_a_id, detection_b_id in predicted_links:
            matched_ids.add(detection_a_id)
            matched_ids.add(detection_b_id)
        unmatched = len(detections) - len(matched_ids)

        return EvaluationResult(
            method=method,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            false_match_rate=round(false_match_rate, 4),
            missed_association_rate=round(missed_rate, 4),
            total_detections=len(detections),
            total_ground_truth_vehicles=len(by_vehicle),
            total_reconstructed_trajectories=0,  # filled by trajectory eval
            correct_associations=tp,
            incorrect_associations=fp,
            missed_associations=fn,
            unmatched_detections=unmatched,
            trajectory_completeness=0.0,
            correct_transitions_pct=0.0,
            per_vehicle_details=[],
        )

    def evaluate_trajectories(
        self,
        trajectories: List[ReconstructedTrajectory],
        detections: List[Detection],
        method: str = "combined",
    ) -> EvaluationResult:
        """
        Evaluate trajectory reconstruction quality.

        A trajectory is "pure" if all its detections belong to the
        same ground-truth vehicle. Completeness measures exact consecutive
        detection links recovered, so repeated camera pairs remain distinct.
        """
        det_map = {d.detection_id: d for d in detections}

        from collections import Counter, defaultdict

        # Ground-truth transitions per vehicle
        gt_vehicle_dets: Dict[str, List[Detection]] = defaultdict(list)
        for d in detections:
            gt_vehicle_dets[d.ground_truth_vehicle_id].append(d)

        # Sort each vehicle's detections by timestamp
        for vid in gt_vehicle_dets:
            gt_vehicle_dets[vid].sort(key=lambda d: (
                d.ground_truth_route_index, d.timestamp
            ))

        gt_transitions = set()
        for vid, dets in gt_vehicle_dets.items():
            for i in range(len(dets) - 1):
                gt_transitions.add((dets[i].detection_id, dets[i + 1].detection_id))

        # Evaluate each trajectory
        predicted_transitions = set()
        pure_trajectories = 0
        per_vehicle: List[Dict] = []

        for traj in trajectories:
            traj_dets = [det_map[did] for did in traj.detection_ids if did in det_map]
            if not traj_dets:
                continue

            gt_ids = [d.ground_truth_vehicle_id for d in traj_dets]
            majority_vid = Counter(gt_ids).most_common(1)[0][0]
            purity = gt_ids.count(majority_vid) / len(gt_ids)
            is_pure = purity == 1.0

            if is_pure:
                pure_trajectories += 1

            # Record exact predicted links in this trajectory.
            traj_dets_sorted = sorted(traj_dets, key=lambda d: d.timestamp)
            for i in range(len(traj_dets_sorted) - 1):
                predicted_transitions.add((
                    traj_dets_sorted[i].detection_id,
                    traj_dets_sorted[i + 1].detection_id,
                ))

            per_vehicle.append({
                "trajectory_id": traj.trajectory_id,
                "majority_vehicle": majority_vid,
                "purity": round(purity, 4),
                "num_detections": len(traj_dets),
                "is_pure": is_pure,
            })

        # Exact pair accounting avoids crediting a correct camera pair from
        # one vehicle to a different vehicle's wrongly linked detections.
        true_positive_pairs = predicted_transitions & gt_transitions
        false_positive_pairs = predicted_transitions - gt_transitions
        missed_pairs = gt_transitions - predicted_transitions
        correct_transitions = len(true_positive_pairs)
        total_transitions = len(predicted_transitions)
        precision = correct_transitions / total_transitions if total_transitions else 0.0
        completeness = correct_transitions / len(gt_transitions) if gt_transitions else 0.0
        linked_detection_ids = {
            detection_id
            for transition in predicted_transitions
            for detection_id in transition
        }

        # Build full result using association-level metrics as base
        vehicle_counts = Counter(d.ground_truth_vehicle_id for d in detections)

        return EvaluationResult(
            method=method,
            precision=round(precision, 4),
            recall=round(completeness, 4),
            f1_score=round(
                2 * precision * completeness / (precision + completeness)
                if (precision + completeness) > 0 else 0.0,
                4,
            ),
            false_match_rate=round(
                len(false_positive_pairs) / total_transitions if total_transitions else 0.0, 4
            ),
            missed_association_rate=round(
                len(missed_pairs) / len(gt_transitions) if gt_transitions else 0.0,
                4,
            ),
            total_detections=len(detections),
            total_ground_truth_vehicles=len(vehicle_counts),
            total_reconstructed_trajectories=len(trajectories),
            correct_associations=correct_transitions,
            incorrect_associations=len(false_positive_pairs),
            missed_associations=len(missed_pairs),
            unmatched_detections=len(set(det_map) - linked_detection_ids),
            trajectory_completeness=round(completeness, 4),
            correct_transitions_pct=round(precision, 4),
            per_vehicle_details=per_vehicle,
        )

    def compare_methods(
        self,
        method_results: Dict[str, EvaluationResult],
    ) -> List[Dict]:
        """
        Build a comparison table across methods.
        """
        rows = []
        for method, result in method_results.items():
            rows.append({
                "Method": method,
                "Precision": result.precision,
                "Recall": result.recall,
                "F1": result.f1_score,
                "Incorrect Transition Rate": result.false_match_rate,
                "Missed Transition Rate": result.missed_association_rate,
                "Correct Assoc.": result.correct_associations,
                "Incorrect Assoc.": result.incorrect_associations,
                "Trajectories": result.total_reconstructed_trajectories,
                "Completeness": result.trajectory_completeness,
            })
        return rows
