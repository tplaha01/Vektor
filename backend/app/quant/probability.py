from __future__ import annotations

import numpy as np


def probability_to_alpha(prob_up: float) -> float:
    """Scale a long probability to a signed alpha score in [-1, 1]."""
    return float(np.clip((float(prob_up) - 0.5) * 2.0, -1.0, 1.0))


def alpha_to_probability(alpha: float) -> float:
    """Invert the signed alpha convention back into a bounded long probability."""
    return float(np.clip((float(alpha) / 2.0) + 0.5, 0.0, 1.0))


def confidence_from_edge(edge: float) -> float:
    return float(np.clip(abs(float(edge)), 0.0, 1.0))
