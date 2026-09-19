from app.extraction import fallback
from app.models import ServiceType


def types(uc):
    return {n.type for n in uc.needs}


def test_demo_sentence():
    uc = fallback.extract("I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight.")
    assert types(uc) == {ServiceType.emergency_housing, ServiceType.food, ServiceType.long_term_assistance}
    assert uc.constraints.age == 19
    assert uc.constraints.budget_usd == 10
    assert uc.constraints.has_car is False
    assert uc.constraints.has_id is None


def test_friend_sentence():
    uc = fallback.extract("My friend needs somewhere to stay tonight, doesn't have a car, and hasn't eaten today.")
    assert ServiceType.emergency_housing in types(uc)
    assert ServiceType.food in types(uc)


def test_family_sentence():
    uc = fallback.extract("Me and my two kids got evicted this morning. I have my ID and about $25 but no car.")
    assert ServiceType.emergency_housing in types(uc)
    assert uc.constraints.family_size == 3
    assert uc.constraints.has_id is True
    assert uc.constraints.budget_usd == 25
    assert uc.constraints.has_car is False


def test_defaults_when_nothing_matches():
    uc = fallback.extract("help")
    assert uc.needs


def test_doesnt_have_a_car():
    uc = fallback.extract("She doesn't have a car and needs a place to sleep.")
    assert uc.constraints.has_car is False
