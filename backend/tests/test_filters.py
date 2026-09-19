from app.models import Constraints, Need, ServiceType, UserConstraints
from app.planner.filters import apply_filters
from app.store import store


def uc(**kw) -> UserConstraints:
    return UserConstraints(needs=[Need(type=ServiceType.emergency_housing), Need(type=ServiceType.food)],
                           constraints=Constraints(**kw))


def reasons(fr):
    return {r.resource_id: r.reason for r in fr.rejected}


def test_age_and_budget_filters():
    fr = apply_filters(store.all_resources(), uc(age=19, budget_usd=10))
    r = reasons(fr)
    assert r["shelter_northern"] == "minimum age 21"
    assert "over budget" in r["hostel_lowcost"]
    assert "shelter_harbor_light" not in r


def test_status_filter():
    fr = apply_filters(store.all_resources(), uc(age=30, budget_usd=50))
    assert reasons(fr)["shelter_westside"] == "currently closed"


def test_id_unknown_is_warning_not_rejection():
    fr = apply_filters(store.all_resources(), uc(age=19, has_id=None))
    assert "shelter_harbor_light" in {r.id for r in fr.eligible}
    assert any("Photo ID" in w for w in fr.warnings["shelter_harbor_light"])
    assert "shelter_harbor_light" not in fr.penalties


def test_id_false_rejects():
    fr = apply_filters(store.all_resources(), uc(age=19, has_id=False))
    assert reasons(fr)["shelter_harbor_light"] == "requires photo ID"


def test_family_filter():
    fr = apply_filters(store.all_resources(), uc(age=30, family_size=3))
    r = reasons(fr)
    assert r["shelter_harbor_light"] == "does not accept families"
    assert "shelter_family_south" not in r


def test_only_needed_services_considered():
    fr = apply_filters(store.all_resources(), uc(age=30))
    assert all(r.service != ServiceType.long_term_assistance for r in fr.eligible)
