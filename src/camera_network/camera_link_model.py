"""
Camera Link Model (CLM).

For a candidate pair of vehicle sightings at two cameras, the CLM evaluates
whether the transition is physically plausible given the camera graph topology
and expected travel-time distributions.

It returns a plausibility score in [0, 1] together with a human-readable
explanation.  A high CLM score does NOT prove that two sightings belong to
the same vehicle — it only indicates that the transition is consistent with
the road network.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from scipy.stats import norm

from src.camera_network.camera_graph import CameraGraph


@dataclass
class CLMResult:
    """Result of a Camera Link Model evaluation."""
    plausibility_score: float        # 0.0 (impossible) … 1.0 (perfectly expected)
    transition_probability: float     # Normalized camera-graph prior for the path
    is_direct_connection: bool       # True if cam_a → cam_b is a single edge
    shortest_hops: Optional[int]     # Shortest path hop count, None if unreachable
    elapsed_seconds: float           # Observed elapsed time
    expected_mean: Optional[float]   # Expected mean travel time for the path
    expected_std: Optional[float]    # Expected std of travel time
    explanation: str                 # Human-readable rationale


class CameraLinkModel:
    """
    Evaluate the plausibility of a vehicle transitioning between two cameras
    given an observed elapsed time.
    """

    def __init__(self, camera_graph: CameraGraph) -> None:
        self.graph = camera_graph
        self._path_profiles = {}
        camera_ids = camera_graph.get_all_camera_ids()
        for cam_a in camera_ids:
            for cam_b in camera_ids:
                if cam_a == cam_b:
                    continue
                path = camera_graph.shortest_path(cam_a, cam_b)
                if not path:
                    self._path_profiles[(cam_a, cam_b)] = None
                    continue

                is_direct = camera_graph.are_directly_connected(cam_a, cam_b)
                hops = len(path) - 1
                path_probability = 1.0
                for index in range(len(path) - 1):
                    path_probability *= camera_graph.get_transition_probability(
                        path[index], path[index + 1]
                    ) or 0.0
                if is_direct:
                    mean_tt, std_tt = camera_graph.get_travel_time_distribution(cam_a, cam_b)
                else:
                    mean_tt = 0.0
                    variance = 0.0
                    for index in range(len(path) - 1):
                        mean, std = camera_graph.get_travel_time_distribution(
                            path[index], path[index + 1]
                        )
                        mean_tt += mean
                        variance += std ** 2
                    std_tt = np.sqrt(variance) if variance > 0 else 60.0
                self._path_profiles[(cam_a, cam_b)] = (
                    is_direct, hops, mean_tt, max(float(std_tt), 1.0), path_probability
                )

    def evaluate(
        self,
        cam_a: str,
        cam_b: str,
        elapsed_seconds: float,
        direction_a: Optional[str] = None,
        direction_b: Optional[str] = None,
    ) -> CLMResult:
        """
        Evaluate whether a transition from *cam_a* to *cam_b* in
        *elapsed_seconds* is plausible.

        Args:
            cam_a: Source camera ID.
            cam_b: Destination camera ID.
            elapsed_seconds: Time between the two detections (seconds).
            direction_a: Exit direction observed at cam_a (optional).
            direction_b: Entry direction observed at cam_b (optional).

        Returns:
            CLMResult with score and explanation.
        """
        # ── Negative elapsed time ───────────────────────────────────────
        if elapsed_seconds < 0:
            return CLMResult(
                plausibility_score=0.0,
                transition_probability=0.0,
                is_direct_connection=False,
                shortest_hops=None,
                elapsed_seconds=elapsed_seconds,
                expected_mean=None,
                expected_std=None,
                explanation=(
                    f"Negative elapsed time ({elapsed_seconds:.1f}s): "
                    f"detection at {cam_b} is BEFORE detection at {cam_a}."
                ),
            )

        # ── Same camera ─────────────────────────────────────────────────
        if cam_a == cam_b:
            # A vehicle re-seen at the same camera
            if elapsed_seconds < 10:
                score = 0.9
                expl = "Same camera, very short gap — likely same pass."
            elif elapsed_seconds < 120:
                score = 0.6
                expl = "Same camera, short gap — possible re-observation."
            else:
                score = 0.3
                expl = "Same camera, long gap — may be a return trip."
            return CLMResult(
                plausibility_score=score,
                transition_probability=1.0,
                is_direct_connection=True,
                shortest_hops=0,
                elapsed_seconds=elapsed_seconds,
                expected_mean=0.0,
                expected_std=0.0,
                explanation=expl,
            )

        # ── Check reachability ──────────────────────────────────────────
        profile = self._path_profiles.get((cam_a, cam_b))
        if profile is None:
            return CLMResult(
                plausibility_score=0.05,
                transition_probability=0.0,
                is_direct_connection=False,
                shortest_hops=None,
                elapsed_seconds=elapsed_seconds,
                expected_mean=None,
                expected_std=None,
                explanation=(
                    f"No path from {cam_a} to {cam_b} in the camera graph. "
                    "Transition highly unlikely (may indicate wrong direction "
                    "or an unmodelled road)."
                ),
            )

        # ── Direct edge: use the edge's travel-time distribution ───────
        is_direct, hops, mean_tt, std_tt, path_probability = profile

        # ── Score from Gaussian CDF ─────────────────────────────────────
        # Use the survival-function-style score: how far is the observed
        # time from the expected mean, relative to the std?
        z_score = abs(elapsed_seconds - mean_tt) / std_tt

        # Gaussian plausibility — peaks at 1.0 when z=0
        gaussian_score = float(np.exp(-0.5 * z_score ** 2))

        # Penalty for impossibly fast travel (< 30 % of mean)
        if elapsed_seconds < mean_tt * 0.3:
            speed_penalty = 0.3
            speed_note = " Penalised for implausibly fast travel."
        elif elapsed_seconds < 0:
            speed_penalty = 0.0
            speed_note = " Penalised: negative elapsed time."
        else:
            speed_penalty = 1.0
            speed_note = ""

        # Penalty for multi-hop (slight discount)
        hop_penalty = 1.0 / (1.0 + 0.1 * max(0, hops - 1))

        # Keep the travel-time likelihood dominant while applying a bounded
        # prior penalty for lower-probability camera-graph branches.
        transition_multiplier = 0.5 + 0.5 * path_probability
        score = gaussian_score * speed_penalty * hop_penalty * transition_multiplier
        score = float(np.clip(score, 0.0, 1.0))

        # ── Direction consistency (soft bonus / penalty) ────────────────
        dir_note = ""
        if direction_a and direction_b:
            cam_a_cfg = self.graph.get_camera(cam_a)
            cam_b_cfg = self.graph.get_camera(cam_b)
            if cam_a_cfg and direction_a not in cam_a_cfg.exit_directions:
                score *= 0.8
                dir_note += (
                    f" Exit direction '{direction_a}' at {cam_a} is unusual."
                )
            if cam_b_cfg and direction_b not in cam_b_cfg.entry_directions:
                score *= 0.8
                dir_note += (
                    f" Entry direction '{direction_b}' at {cam_b} is unusual."
                )

        score = float(np.clip(score, 0.0, 1.0))

        explanation = (
            f"Path {cam_a}→{cam_b} ({hops} hop{'s' if hops != 1 else ''}). "
            f"Elapsed {elapsed_seconds:.0f}s vs expected "
            f"{mean_tt:.0f}±{std_tt:.0f}s (z={z_score:.2f}); "
            f"path prior {path_probability:.3f}. "
            f"Score {score:.3f}.{speed_note}{dir_note}"
        )

        return CLMResult(
            plausibility_score=score,
            transition_probability=float(path_probability),
            is_direct_connection=is_direct,
            shortest_hops=hops,
            elapsed_seconds=elapsed_seconds,
            expected_mean=mean_tt,
            expected_std=std_tt,
            explanation=explanation,
        )

    def is_candidate_transition(
        self, cam_a: str, cam_b: str, elapsed_seconds: float, max_gap_seconds: float
    ) -> bool:
        """Cheap conservative gate for pairs whose CLM score could exceed 0.05.

        The bound is intentionally wider than the scorer's practical acceptance
        range so this prefilter does not remove plausible transitions.
        """
        bounds = self.candidate_time_bounds(cam_a, cam_b, max_gap_seconds)
        return bounds is not None and bounds[0] <= elapsed_seconds <= bounds[1]

    def candidate_time_bounds(
        self, cam_a: str, cam_b: str, max_gap_seconds: float
    ) -> Optional[Tuple[float, float]]:
        """Return a conservative elapsed-time range that may pass CLM gating."""
        if cam_a == cam_b:
            return (10.0, max_gap_seconds) if max_gap_seconds >= 10.0 else None
        profile = self._path_profiles.get((cam_a, cam_b))
        if profile is None:
            return None
        _, _, mean_tt, std_tt, _ = profile
        z_limit = 2.5
        earliest = max(0.0, mean_tt - z_limit * std_tt)
        latest = min(max_gap_seconds, mean_tt + z_limit * std_tt)
        return (earliest, latest) if earliest <= latest else None
