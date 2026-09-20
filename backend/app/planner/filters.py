from __future__ import annotations

from dataclasses import dataclass, field

from ..models import RejectedResource, Resource, ResourceStatus, ServiceType, UserConstraints


@dataclass
class FilterResult:
    eligible: list[Resource]
    rejected: list[RejectedResource]
    warnings: dict[str, list[str]] = field(default_factory=dict)
    penalties: dict[str, float] = field(default_factory=dict)


STATUS_REASON = {
    ResourceStatus.full: "currently full",
    ResourceStatus.closed: "currently closed",
    ResourceStatus.unavailable: "currently unavailable",
    ResourceStatus.delayed: "service delayed today",
}


def apply_filters(resources: list[Resource], uc: UserConstraints) -> FilterResult:
    needed: set[ServiceType] = {n.type for n in uc.needs}
    c = uc.constraints
    eligible: list[Resource] = []
    rejected: list[RejectedResource] = []
    warnings: dict[str, list[str]] = {}
    penalties: dict[str, float] = {}

    for r in resources:
        if r.service not in needed:
            continue
        reason = None
        e = r.eligibility

        if r.status != ResourceStatus.available:
            reason = STATUS_REASON.get(r.status, "unavailable")
        elif r.capacity is not None and r.capacity < c.family_size:
            reason = "not enough available places for your household"
        elif c.children and e.children_ok is not True:
            reason = "cannot confirm this resource accepts children"
        elif c.pets and e.pets_ok is not True:
            reason = "cannot confirm this resource accepts pets"
        elif any(a != "limited_walking" and a not in e.accessibility for a in c.accessibility):
            reason = "required accessibility support is not confirmed"
        elif c.age is not None and e.min_age is not None and c.age < e.min_age:
            reason = f"minimum age {e.min_age}"
        elif c.age is not None and e.max_age is not None and c.age > e.max_age:
            reason = f"maximum age {e.max_age}"
        elif e.requires_id and c.has_id is False:
            reason = "requires photo ID"
        elif c.budget_usd is not None and r.cost > c.budget_usd:
            reason = f"costs ${r.cost:.0f}, over budget"
        elif not e.families_ok and c.family_size > 1:
            reason = "does not accept families"
        elif "families_only" in r.tags and c.family_size <= 1:
            reason = "families with children only"
        elif e.gender and c.gender in ("male", "female") and e.gender != c.gender:
            reason = f"{e.gender}-only"

        if reason:
            rejected.append(RejectedResource(resource_id=r.id, name=r.name, service=r.service, reason=reason))
            continue

        w: list[str] = []
        pen = 0.0
        if c.age is None and (e.min_age is not None or e.max_age is not None):
            w.append("Age requirement — confirm eligibility before traveling")
        if e.requires_id and c.has_id is None:
            w.append("Photo ID required — confirm you have one")
        if e.gender and c.gender not in ("male", "female"):
            w.append(f"{e.gender.capitalize()}-only — confirm eligibility")
            pen += 0.15
        if r.capacity is not None and r.capacity <= 3:
            w.append(f"Only {r.capacity} spots reported — call ahead")
            pen += 0.05
        if w:
            warnings[r.id] = w
        if pen:
            penalties[r.id] = pen
        eligible.append(r)

    return FilterResult(eligible=eligible, rejected=rejected, warnings=warnings, penalties=penalties)
