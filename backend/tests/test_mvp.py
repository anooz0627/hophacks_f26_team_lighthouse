"""End-to-end contract and planner regression tests for the interactive vertical slice."""
from datetime import datetime
import os
os.environ["LIGHTHOUSE_DISABLE_LLM"] = "1"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import Constraints, Need, ResourceStatus, ServiceType, UserConstraints
from app.extraction.fallback import extract
from app.planner.service import make_plan, make_bundle
from app.store import store

client = TestClient(app)
NOW = datetime(2026, 9, 17, 18)
SCENARIO = "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight."


def test_review_then_multiple_real_strategies():
    extracted = client.post('/extract', json={'text': SCENARIO}).json()
    assert {n['type'] for n in extracted['needs']} == {'emergency_housing', 'food', 'long_term_assistance'}
    result = client.post('/plans', json={'constraints': extracted, 'now': NOW.isoformat()})
    assert result.status_code == 200
    plans = result.json()['plans']
    assert len(plans) >= 2
    assert plans[0]['resource_ids'][1] == 'shelter_harbor_light'
    for plan in plans:
        assert plan['feasible'] and plan['total_cost_usd'] <= 10
        assert sum(s['cost_usd'] for s in plan['steps']) == plan['total_cost_usd']
        assert [s['time_iso'] for s in plan['steps']] == sorted(s['time_iso'] for s in plan['steps'])
        assert plan['tradeoff']
    fastest = next(p for p in plans if p['strategy'] == 'fastest')
    assert fastest['total_travel_min'] <= plans[0]['total_travel_min']


def test_reviewed_values_override_original_text():
    uc = extract(SCENARIO)
    uc.constraints.has_id = False
    uc.constraints.budget_usd = 0
    uc.constraints.transport = 'walking'
    result = client.post('/plans', json={'constraints': uc.model_dump(mode='json'), 'now': NOW.isoformat()})
    assert result.status_code == 200
    for p in result.json()['plans']:
        assert 'shelter_harbor_light' not in p['resource_ids']
        assert p['constraints']['constraints']['budget_usd'] == 0
        assert all(s['mode'] == 'walk' for s in p['steps'] if s['type'] == 'travel')
        assert p['total_cost_usd'] == 0


@pytest.mark.parametrize('status', ['full', 'closed', 'unavailable', 'delayed'])
def test_each_unavailable_status_invalidates_and_replaces(status):
    uc = extract(SCENARIO)
    old = make_bundle(uc, NOW).plans[0]
    rid = next(rid for rid in old.resource_ids if store.get(rid).service == ServiceType.emergency_housing)
    assert client.patch(f'/resources/{rid}/status', json={'status': status}).status_code == 200
    result = make_bundle(uc, NOW, old.plan_id)
    assert rid in result.diff.removed_resource_ids
    assert status in result.diff.trigger
    assert result.plans[0].feasible
    assert result.diff.added_resource_ids
    assert result.diff.travel_delta_min == result.plans[0].total_travel_min - old.total_travel_min
    assert all(rid not in p.resource_ids for p in result.plans)


def test_later_only_request_has_a_real_timeline():
    uc = UserConstraints(needs=[Need(type=ServiceType.long_term_assistance, deadline='tomorrow')], constraints=Constraints(age=19, budget_usd=0))
    plan = make_plan(uc, NOW)
    assert plan.feasible and plan.resource_ids
    assert all(s.time_iso >= NOW.isoformat() for s in plan.steps)
    assert plan.total_cost_usd == sum(s.cost_usd for s in plan.steps)


def test_later_service_fee_cannot_escape_budget():
    for r in store.all_resources():
        if r.service == ServiceType.long_term_assistance:
            r.cost = 11
    uc = extract(SCENARIO)
    plan = make_plan(uc, NOW)
    assert not plan.feasible
    assert ServiceType.long_term_assistance in plan.unmet_needs
    assert plan.total_cost_usd <= 10


def test_zero_capacity_is_not_usable_and_reset_restores_it():
    client.patch('/resources/shelter_harbor_light/status', json={'status': 'available', 'capacity': 0})
    assert 'shelter_harbor_light' not in make_plan(extract(SCENARIO), NOW).resource_ids
    client.post('/resources/reset')
    assert store.get('shelter_harbor_light').capacity == 4


def test_pets_and_accessibility_are_enforced():
    uc = extract(SCENARIO + ' I have my dog and need hearing support.')
    assert uc.constraints.pets and 'hearing_support' in uc.constraints.accessibility
    plan = make_plan(uc, NOW)
    for rid in plan.resource_ids:
        assert store.get(rid).eligibility.pets_ok
        assert 'hearing_support' in store.get(rid).eligibility.accessibility
    assert not plan.feasible  # no seeded food service has both policies confirmed


def test_children_never_route_to_single_adult_shelters():
    uc = extract('Me and my two kids got evicted. I have my ID, $25, no car, and need dinner tonight.')
    assert uc.constraints.children and uc.constraints.family_size == 3
    plan = make_plan(uc, NOW)
    assert plan.resource_ids
    assert all(store.get(rid).eligibility.children_ok for rid in plan.resource_ids)
    assert all(store.get(rid).capacity is None or store.get(rid).capacity >= 3 for rid in plan.resource_ids)


def test_custom_deadline_and_walking_limit():
    uc = extract(SCENARIO)
    for need in uc.needs:
        need.deadline = 'custom'
    uc.constraints.custom_deadline = NOW.replace(hour=18, minute=10)
    plan = make_plan(uc, NOW)
    assert all(datetime.fromisoformat(s.time_iso) <= uc.constraints.custom_deadline for s in plan.steps)
    assert not plan.feasible
    uc.constraints.accessibility = ['limited_walking']
    uc.constraints.transport = 'walking'
    uc.constraints.custom_deadline = NOW.replace(hour=23)
    plan = make_plan(uc, NOW)
    assert all(s.duration_min <= 8 for s in plan.steps if s.type == 'travel')


def test_this_week_never_mislabels_monday_as_tomorrow():
    uc = UserConstraints(needs=[Need(type=ServiceType.long_term_assistance, deadline='this_week')], constraints=Constraints(age=19))
    plan = make_plan(uc, datetime(2026,9,19,18))
    assert plan.feasible
    assert all(s.day_label == 'later' for s in plan.steps)
    assert all(s.time_iso.startswith('2026-09-21') for s in plan.steps)


def test_empty_and_invalid_requests_fail_with_useful_status():
    assert client.post('/extract', json={'text': ''}).status_code == 422
    assert client.post('/plans', json={'constraints': {'needs': [], 'constraints': {}}, 'now': NOW.isoformat()}).status_code == 422
    uc = extract(SCENARIO).model_dump(mode='json')
    uc['constraints']['budget_usd'] = -1
    assert client.post('/plans', json={'constraints': uc}).status_code == 422
    assert client.patch('/resources/shelter_harbor_light/status', json={'status': 'available', 'capacity': -1}).status_code == 422


def test_resource_sources_are_structured_and_not_fake_websites():
    resources = client.get('/resources').json()
    for r in resources:
        assert r['simulated']
        assert r['website_url'] is None
        assert 'example.org' not in str(r)
        assert client.get(f'/resources/{r["id"]}').status_code == 200


def test_timezone_is_baltimore_regardless_of_host():
    local = make_plan(extract(SCENARIO), NOW)
    utc = make_plan(extract(SCENARIO), datetime.fromisoformat('2026-09-17T22:00:00+00:00'))
    assert local.resource_ids == utc.resource_ids
    assert local.now == utc.now


def test_all_full_is_explicitly_partial():
    for r in store.all_resources():
        if r.service == ServiceType.emergency_housing:
            store.set_status(r.id, ResourceStatus.full)
    bundle = make_bundle(extract(SCENARIO), NOW)
    assert all(not p.feasible for p in bundle.plans)
    assert all(ServiceType.emergency_housing in p.unmet_needs for p in bundle.plans)


def test_food_scenario_parses_walking_and_neighborhood():
    uc = extract("I'm 22, in Mount Vernon. I need food tonight, have no money, and can only walk.")
    assert uc.constraints.transport == 'walking'
    assert uc.constraints.location_label == 'Mount Vernon'
    assert uc.constraints.budget_usd == 0


@pytest.mark.parametrize('text', [
    "I'm one person and need food tonight.",
    "I need food, with no children or pets.",
    "I don't have any kids. I need food.",
])
def test_child_mentions_require_whole_words_and_respect_negation(text):
    uc = extract(text)
    assert not uc.constraints.children
    assert uc.constraints.family_size == 1


def test_household_counts_children_and_partner():
    uc = extract('My partner and my two children need food with me tonight.')
    assert uc.constraints.children
    assert uc.constraints.family_size == 4


@pytest.mark.parametrize('money', ['$1,000.50', '1,000.50 dollars'])
def test_formatted_budgets_are_not_truncated(money):
    assert extract(f'I need food and have {money}.').constraints.budget_usd == 1000.50


@pytest.mark.parametrize('age', [9, 100, 120])
def test_supported_ages_survive_extraction(age):
    assert extract(f"I'm {age} and need food.").constraints.age == age


@pytest.mark.parametrize('text', ['   ', 'I need food and have $100001.', 'I need food and have $-5.', "I'm 121 and need food."])
@pytest.mark.parametrize('endpoint', ['/extract', '/plan'])
def test_bad_situation_values_are_validation_errors(endpoint, text):
    result = client.post(endpoint, json={'text': text})
    assert result.status_code == 422
    assert result.json()['detail']


@pytest.mark.parametrize(('wording', 'deadline'), [
    ('tonight', 'tonight'), ('tomorrow', 'tomorrow'),
    ('this week', 'this_week'), ('within 24 hours', 'within_24_hours'),
])
def test_explicit_long_term_only_deadline_is_preserved(wording, deadline):
    uc = extract(f'I need housing assistance {wording}.')
    assert len(uc.needs) == 1
    assert uc.needs[0].deadline == deadline


def test_legacy_endpoint_validates_dates():
    result = client.post('/plan/from-constraints?now=not-a-date', json=extract(SCENARIO).model_dump(mode='json'))
    assert result.status_code == 422


@pytest.mark.parametrize(('mode', 'allowed'), [
    ('no_vehicle', {'walk', 'bus'}), ('public_transit', {'walk', 'bus'}),
    ('walking', {'walk'}), ('rideshare', {'rideshare'}), ('own_vehicle', {'car'}),
])
def test_each_transport_choice_controls_plan_legs(mode, allowed):
    uc = UserConstraints(needs=[Need(type=ServiceType.food)], constraints=Constraints(age=22, budget_usd=50, transport=mode))
    plan = make_plan(uc, NOW)
    assert plan.feasible
    legs = [s for s in plan.steps if s.type == 'travel']
    assert legs and all(s.mode in allowed for s in legs)
    assert plan.total_cost_usd == sum(s.cost_usd for s in plan.steps)


def test_household_fares_and_rideshare_vehicle_count():
    from app.planner.travel import travel_options
    a, b = (39.291, -76.6215), (39.31, -76.579)
    solo = travel_options(a, b, Constraints(family_size=1), store.transit)
    family = travel_options(a, b, Constraints(family_size=3), store.transit)
    solo_bus = {s.route_id: s.cost_usd for s in solo if s.mode == 'bus'}
    assert solo_bus
    assert all(s.cost_usd == 3 * solo_bus[s.route_id] for s in family if s.mode == 'bus')
    ride = travel_options(a, b, Constraints(transport='rideshare'), store.transit)[0]
    two_cars = travel_options(a, b, Constraints(transport='rideshare', family_size=5), store.transit)[0]
    assert abs(two_cars.cost_usd - 2 * ride.cost_usd) <= .01


def test_custom_deadline_requires_a_date():
    uc = extract(SCENARIO)
    uc.needs[0].deadline = 'custom'
    result = client.post('/plans', json={'constraints': uc.model_dump(mode='json')})
    assert result.status_code == 422


def test_all_resources_unavailable_yields_no_actions():
    for resource in store.all_resources():
        store.set_status(resource.id, ResourceStatus.unavailable)
    bundle = make_bundle(extract(SCENARIO), NOW)
    assert len(bundle.plans) == 1
    assert not bundle.plans[0].feasible
    assert not bundle.plans[0].resource_ids
    assert all(s.type == 'note' for s in bundle.plans[0].steps)


def test_explicit_transport_preference_overrides_car_ownership():
    uc = UserConstraints(needs=[Need(type=ServiceType.food)], constraints=Constraints(has_car=True, transport='walking'))
    plan = make_plan(uc, NOW)
    assert plan.feasible
    assert all(s.mode == 'walk' for s in plan.steps if s.type == 'travel')
