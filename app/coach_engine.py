"""
Coach App - Backend Engine with FIFO Action History Persistence
================================================================
Manages:
  1. Model loading (XGBoost model.joblib + model_config.json)
  2. FIFO 3-day action history via Kivy's local JSON config storage
  3. Three-scenario simulation: sweeps action_lag_1 (today's decision),
     keeps action_lag_2 and action_lag_3 fixed from stored history

Local Storage Layout (coach_history.json):
  {
    "action_lag_1": 0,   ← yesterday (most recent)
    "action_lag_2": 1,   ← two days ago
    "action_lag_3": 2    ← three days ago
  }
  Values: 0=Rest, 1=Easy, 2=Hard
"""

import json
import os
from pathlib import Path
from typing import Optional

# numpy, pandas, joblib are imported lazily inside load()/simulate()
# to avoid uncatchable native library crashes at module level on Android.


# ---------------------------------------------------------------------------
# File resolution — works both on PC and inside a compiled Kivy APK
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_PARENT = _HERE.parent

SEARCH_PATHS = [
    _HERE / "model.joblib",
    _PARENT / "model.joblib",
]
CONFIG_PATHS = [
    _HERE / "model_config.json",
    _PARENT / "model_config.json",
]

# History file — prefer writable Android private dir, fall back to app dir
_ANDROID_PRIVATE = os.environ.get('ANDROID_PRIVATE', '')
HISTORY_PATHS = [
    Path(_ANDROID_PRIVATE) / 'coach_history.json' if _ANDROID_PRIVATE else None,
    _HERE / 'coach_history.json',
    _PARENT / 'coach_history.json',
]
HISTORY_PATHS = [p for p in HISTORY_PATHS if p is not None]

ACTION_ENCODE = {"Rest": 0, "Easy": 1, "Hard": 2}
ACTION_DECODE = {0: "Rest", 1: "Easy", 2: "Hard"}
DEFAULT_HISTORY = {"action_lag_1": 0, "action_lag_2": 0, "action_lag_3": 0}


# ---------------------------------------------------------------------------
# History persistence helpers
# ---------------------------------------------------------------------------

def _history_path() -> Path:
    """Return the writable history file path."""
    # Prefer the first path that already exists, otherwise use _HERE
    for p in HISTORY_PATHS:
        if p.exists():
            return p
    return HISTORY_PATHS[0]


def load_history() -> dict:
    """
    Load the 3-day action history from local JSON.
    Returns default all-Rest history if the file doesn't exist yet.
    """
    path = _history_path()
    if not path.exists():
        return dict(DEFAULT_HISTORY)
    try:
        with open(path, "r") as f:
            data = json.load(f)
        # Validate keys and values
        validated = {}
        for key in ("action_lag_1", "action_lag_2", "action_lag_3"):
            val = data.get(key, 0)
            validated[key] = int(val) if val in (0, 1, 2) else 0
        return validated
    except Exception:
        return dict(DEFAULT_HISTORY)


def save_history(history: dict) -> None:
    """Persist the 3-day action history to local JSON."""
    path = _history_path()
    try:
        with open(path, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save history: {e}")


def advance_history(yesterday_action_name: str) -> dict:
    """
    FIFO cycle: push yesterday's action into the front of the queue.

    Before:  lag_1=A  lag_2=B  lag_3=C
    After:   lag_1=yesterday  lag_2=A  lag_3=B
    (C is dropped — it's now 4 days ago)

    Args:
        yesterday_action_name: "Rest", "Easy", or "Hard"

    Returns:
        The updated history dict (already saved to disk).
    """
    yesterday_encoded = ACTION_ENCODE.get(yesterday_action_name, 0)
    old = load_history()

    new_history = {
        "action_lag_1": yesterday_encoded,       # yesterday → now lag_1
        "action_lag_2": old["action_lag_1"],     # old lag_1 → lag_2
        "action_lag_3": old["action_lag_2"],     # old lag_2 → lag_3
        # old lag_3 is discarded
    }
    save_history(new_history)
    return new_history


def get_history_labels() -> dict:
    """Return history as human-readable labels for display."""
    hist = load_history()
    return {
        "yesterday": ACTION_DECODE.get(hist["action_lag_1"], "Rest"),
        "2_days_ago": ACTION_DECODE.get(hist["action_lag_2"], "Rest"),
        "3_days_ago": ACTION_DECODE.get(hist["action_lag_3"], "Rest"),
    }


# ---------------------------------------------------------------------------
# Model engine
# ---------------------------------------------------------------------------

def _find_file(paths: list) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


class CoachEngine:
    """
    Wraps the trained XGBoost model for offline use in the mobile app.
    Handles model loading, FIFO history management, and simulation.
    """

    FEATURE_LABELS = {
        "hrv_rmssd":                   "Morning HRV (RMSSD, ms)",
        "resting_hr":                  "Resting Heart Rate (BPM)",
        "sleep_overall_score":         "Sleep Score (0-100)",
        "sleep_deep_minutes":          "Deep Sleep (minutes)",
        "sleep_minutes":               "Total Sleep (minutes)",
        "sleep_restlessness":          "Sleep Restlessness (0-1)",
        "stress_score":                "Stress Score (0-100)",
        "hrv_7d":                      "7-Day Avg HRV",
        "hrv_28d":                     "28-Day Avg HRV",
        "hrv_ratio":                   "HRV Ratio (7d / 28d)",
        "hrv_7d_trend":                "HRV 7-Day Trend",
        "rhr_7d":                      "7-Day Avg Resting HR",
        "ctl":                         "Fitness (CTL)",
        "atl":                         "Fatigue (ATL)",
        "tsb":                         "Form (TSB = CTL − ATL)",
        "prev_tss":                    "Yesterday's TSS",
        "prev_ef":                     "Yesterday's Efficiency Factor",
        "prev_stream_variability_index": "Yesterday's Power Variability",
        "prev_stream_cardiac_drift":   "Yesterday's Cardiac Drift",
        "prev_stream_coasting_ratio":  "Yesterday's Coasting Ratio",
        "sleep_score_7d":              "7-Day Sleep Score Avg",
        # The action lags are managed internally — not shown as manual inputs
        "action_lag_1":                "(auto) Yesterday's Action",
        "action_lag_2":                "(auto) 2 Days Ago Action",
        "action_lag_3":                "(auto) 3 Days Ago Action",
    }

    ACTION_COLORS = {
        "Rest": (0.25, 0.75, 0.35, 1),
        "Easy": (0.22, 0.55, 0.9,  1),
        "Hard": (0.9,  0.28, 0.18, 1),
    }

    def __init__(self):
        self.model = None
        self.config = None
        self.feature_columns = []
        self.top_features = []
        self.loaded = False
        self.error_message = ""

    def load(self) -> bool:
        """Load model and config. Returns True on success."""
        # Lazy imports — kept here so native .so crashes are catchable
        try:
            import numpy as np          # noqa: F401 (used in simulate)
            import pandas as pd         # noqa: F401 (used in simulate)
            import joblib as _joblib
        except Exception as e:
            self.error_message = f"Failed to import data libraries: {e}"
            return False

        model_path = _find_file(SEARCH_PATHS)
        config_path = _find_file(CONFIG_PATHS)

        if model_path is None:
            self.error_message = (
                "model.joblib not found.\n"
                f"Searched: {[str(p) for p in SEARCH_PATHS]}"
            )
            return False

        if config_path is None:
            self.error_message = (
                "model_config.json not found.\n"
                f"Searched: {[str(p) for p in CONFIG_PATHS]}"
            )
            return False

        try:
            self.model = _joblib.load(model_path)
            with open(config_path, "r") as f:
                self.config = json.load(f)
            self.feature_columns = self.config.get("feature_columns", [])
            self.top_features = self.config.get("top_feature_names", [])
            self.loaded = True
            return True
        except Exception as e:
            self.error_message = f"Error loading model: {e}"
            return False

    def simulate(self, morning_inputs: dict) -> dict:
        """
        Run three-scenario simulation using a hybrid approach:

        1. XGBoost base prediction: predicts next_workout_ef_delta from
           morning wellness features (HRV, RHR, sleep, stress, CTL/ATL/TSB).
           This captures the physiological readiness signal.

        2. Sports-science fatigue-recovery adjustment: adds a principled
           adjustment based on the action lag sequence using Banister
           impulse-response principles:
             - Recent Hard efforts increase ATL (fatigue) → reduce performance
             - Recent Rest periods allow supercompensation → boost performance
             - Easy days maintain fitness without adding fatigue

        The combination gives directionally correct scenario differences even
        when the base model's action-lag coefficients are near zero (as expected
        with limited training data).

        Args:
            morning_inputs: dict of {feature_name: float}
                            All wellness inputs EXCEPT action lags.

        Returns:
            {
                "recommended_action": "Easy",
                "readiness_score": 72,          # 0-100 composite
                "scores": {"Rest": 0.012, "Easy": 0.025, "Hard": -0.008},
                "interpretation": {...},
                "confidence": "high",
                "history_used": {"lag_2": "Easy", "lag_3": "Rest"}
            }
        """
        if not self.loaded:
            raise RuntimeError("Engine not loaded. Call load() first.")

        import numpy as np
        import pandas as pd

        history = load_history()
        lag_1_stored = history["action_lag_1"]   # yesterday's actual action
        lag_2 = history["action_lag_2"]           # 2 days ago
        lag_3 = history["action_lag_3"]           # 3 days ago

        # ------------------------------------------------------------------
        # Step 1: XGBoost base prediction for each scenario
        # The model's wellness features (HRV, CTL, sleep, etc.) capture the
        # physiological readiness dimension.
        # ------------------------------------------------------------------
        model_scores = {}
        for action_name, action_code in ACTION_ENCODE.items():
            inputs = morning_inputs.copy()
            inputs["action_lag_1"] = float(action_code)
            inputs["action_lag_2"] = float(lag_2)
            inputs["action_lag_3"] = float(lag_3)

            row = np.array(
                [inputs.get(col, np.nan) for col in self.feature_columns],
                dtype=float,
            )
            X = pd.DataFrame([row], columns=self.feature_columns)
            model_scores[action_name] = float(self.model.predict(X)[0])

        # ------------------------------------------------------------------
        # Step 2: Sports-science fatigue-recovery adjustment
        # Based on Banister impulse-response model principles:
        #   fatigue_load = ATL signal from recent training
        #   fitness_benefit = CTL signal (positive lag ~14d)
        #
        # Recent action sequence effects on NEXT workout EF delta:
        #   Hard (2): adds significant fatigue → suppresses next EF by ~0.03
        #   Easy (1): mild fatigue → neutral effect (~0.01)
        #   Rest (0): recovery → boosts next EF by ~0.02
        #
        # Lag weights decay with recency (lag_1 most relevant):
        #   lag_1 (yesterday): weight 1.0
        #   lag_2 (2d ago):    weight 0.5
        #   lag_3 (3d ago):    weight 0.25
        #
        # EF_delta_adj = SUM(lag_w * action_effect) for lags 1,2,3
        # ------------------------------------------------------------------
        ACTION_EFFECT = {0: +0.020, 1: -0.008, 2: -0.025}  # Rest=recovery, Hard=fatigue
        LAG_WEIGHTS = {1: 1.0, 2: 0.5, 3: 0.25}

        # Baseline adjustment from stored history (lags 2 and 3 are fixed)
        history_adj = (
            LAG_WEIGHTS[2] * ACTION_EFFECT.get(lag_2, 0) +
            LAG_WEIGHTS[3] * ACTION_EFFECT.get(lag_3, 0)
        )

        scenario_adj = {}
        for action_name, action_code in ACTION_ENCODE.items():
            # Lag_1 is the decision variable (what we're choosing today)
            scenario_adj[action_name] = (
                LAG_WEIGHTS[1] * ACTION_EFFECT.get(action_code, 0) +
                history_adj
            )

        # ------------------------------------------------------------------
        # Step 3: Combine model score + sports-science adjustment
        # Weight: 60% model (captures current readiness state),
        #         40% sports science (captures action choice effect)
        # ------------------------------------------------------------------
        MODEL_WEIGHT = 0.60
        SCIENCE_WEIGHT = 0.40

        # Normalize the model scores to the same scale as the adjustments
        # (both are EF delta units, ~-0.05 to +0.05)
        model_base = np.mean(list(model_scores.values()))
        combined = {}
        for action in ACTION_ENCODE:
            combined[action] = (
                MODEL_WEIGHT * model_scores[action] +
                SCIENCE_WEIGHT * scenario_adj[action]
            )

        best_action = max(combined, key=combined.get)
        score_vals = list(combined.values())
        spread = max(score_vals) - min(score_vals)

        # ------------------------------------------------------------------
        # Step 4: Readiness score (0-100)
        # Based on top SHAP features: HRV ratio, sleep, stress, TSB
        # ------------------------------------------------------------------
        readiness = self._compute_readiness_score(morning_inputs)

        def interpret(s):
            if s > 0.015:    return "Strong Performance Gain Expected"
            elif s > 0.005:  return "Performance Gain Likely"
            elif s > -0.005: return "Stable / Maintenance"
            elif s > -0.015: return "Performance Dip Likely"
            else:            return "Recovery Needed"

        return {
            "recommended_action": best_action,
            "readiness_score": readiness,
            "scores": combined,
            "raw_model_scores": model_scores,
            "interpretation": {k: interpret(v) for k, v in combined.items()},
            "confidence": (
                "high"     if spread > 0.03
                else "moderate" if spread > 0.015
                else "low"
            ),
            "spread": spread,
            "history_used": {
                "lag_2": ACTION_DECODE.get(lag_2, "Rest"),
                "lag_3": ACTION_DECODE.get(lag_3, "Rest"),
            },
        }

    def _compute_readiness_score(self, inputs: dict) -> int:
        """
        Compute a 0-100 readiness score from physiological inputs.

        Based on SHAP-identified top features:
          - HRV 7d (most important): above/below 28d baseline
          - Sleep score 28d trend: chronic sleep quality
          - Stress ratio: acute vs chronic stress load
          - CTL: base fitness level (higher = more capacity)
          - TSB: form (positive = fresher, negative = fatigued)

        Returns an integer 0-100.
        """
        score = 50.0  # neutral baseline

        # HRV signal: ratio of 7d avg to 28d avg
        hrv_7d = inputs.get("hrv_7d", np.nan)
        hrv_28d = inputs.get("hrv_28d", np.nan)
        hrv_rmssd = inputs.get("hrv_rmssd", np.nan)
        if not np.isnan(hrv_7d) and not np.isnan(hrv_28d) and hrv_28d > 0:
            hrv_ratio = hrv_7d / hrv_28d
            score += (hrv_ratio - 1.0) * 40   # ±0.1 ratio → ±4 points
        elif not np.isnan(hrv_rmssd):
            # Use absolute HRV as proxy (typical range 20-70ms)
            score += (hrv_rmssd - 40) * 0.3

        # Sleep score
        sleep = inputs.get("sleep_overall_score", np.nan)
        if not np.isnan(sleep):
            score += (sleep - 75) * 0.4   # each point above 75 = +0.4

        # Stress ratio (lower = better recovery)
        stress_ratio = inputs.get("stress_ratio", np.nan)
        if not np.isnan(stress_ratio):
            score -= (stress_ratio - 1.0) * 10  # above baseline hurts

        # TSB (form)
        tsb = inputs.get("tsb", np.nan)
        if not np.isnan(tsb):
            score += tsb * 0.3  # +10 TSB → +3 points

        # CTL (fitness base)
        ctl = inputs.get("ctl", np.nan)
        if not np.isnan(ctl):
            score += (ctl - 40) * 0.1   # above base fitness level

        return int(max(0, min(100, score)))


    def commit_yesterday_action(self, action_name: str) -> dict:
        """
        Called when the user confirms yesterday's action.
        Advances the FIFO queue and saves to disk.

        Returns the updated history for UI confirmation display.
        """
        new_history = advance_history(action_name)
        return {k: ACTION_DECODE.get(v, "Rest") for k, v in new_history.items()}

    def get_wellness_feature_info(self) -> list[dict]:
        """
        Return info about the manual wellness input fields.
        Excludes action_lag_* columns (auto-filled from storage).
        """
        # Filter top features to exclude the lag columns (they're auto-managed)
        manual_features = [
            f for f in self.top_features
            if "action_lag" not in f
        ]

        result = []
        for feat in manual_features:
            info = {
                "feature": feat,
                "label": self.FEATURE_LABELS.get(feat, feat.replace("_", " ").title()),
            }
            # Suggest sensible defaults and hints
            if "hrv" in feat and "ratio" not in feat and "trend" not in feat:
                info.update(hint="Typical: 20–80 ms", default=40.0)
            elif "resting_hr" in feat or feat == "rhr_7d":
                info.update(hint="Typical: 45–70 BPM", default=55.0)
            elif "sleep" in feat and "score" in feat:
                info.update(hint="0–100", default=75.0)
            elif "sleep_minutes" in feat:
                info.update(hint="e.g. 420 = 7 hours", default=420.0)
            elif feat == "tsb":
                info.update(hint="CTL − ATL, typically −20 to +20", default=0.0)
            elif feat == "ctl":
                info.update(hint="Chronic Training Load (20–100)", default=50.0)
            elif feat == "atl":
                info.update(hint="Acute Training Load (10–120)", default=50.0)
            elif "stress" in feat:
                info.update(hint="0–100 (100 = most stressed)", default=75.0)
            else:
                info.update(hint="", default=0.0)
            result.append(info)
        return result
