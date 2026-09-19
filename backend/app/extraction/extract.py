from __future__ import annotations

from ..models import UserConstraints
from . import fallback, llm

PRESERVED_FIELDS = ("children", "pets", "accessibility", "transport", "transportation_needed",
                    "location_label", "current_location")


def extract(text: str) -> UserConstraints:
    uc = llm.extract(text)
    if uc is not None and uc.needs:
        rules = fallback.extract(text)
        for name in PRESERVED_FIELDS:
            setattr(uc.constraints, name, getattr(rules.constraints, name))
        for need in rules.needs:
            if need.type not in {n.type for n in uc.needs}:
                uc.needs.append(need)
        return uc
    return fallback.extract(text)
