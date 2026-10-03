"""Photo-tier scale / confidence from still count and priors (brief §5.4)."""

from __future__ import annotations

CEILING_PRIOR_M = (2.4, 3.2)
DOOR_HEIGHT_PRIOR_M = (2.0, 2.1)
CAMERA_HEIGHT_PRIOR_M = (1.3, 1.6)
CAMERA_HEIGHT_REF_M = 1.45


def photo_scale_sigma_rel(n_photos: int, *, vlm_used: bool) -> float:
    base = 0.14 if vlm_used else 0.18
    base += max(0, 5 - n_photos) * 0.025
    return min(base, 0.35)


def ceiling_in_prior(ceiling_m: float) -> bool:
    return CEILING_PRIOR_M[0] - 0.3 <= ceiling_m <= CEILING_PRIOR_M[1] + 0.4


def prior_warnings(ceiling_m: float) -> list[str]:
    if ceiling_in_prior(ceiling_m):
        return []
    return ["photo: ceiling outside typical prior 2.4–3.2 m; intervals widened"]
