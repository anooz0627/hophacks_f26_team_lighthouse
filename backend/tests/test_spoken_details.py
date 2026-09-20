import pytest

from app.extraction import fallback, llm
from app.extraction.extract import extract
from app.main import app
from app.models import Constraints, Need, ServiceType, UserConstraints
from fastapi.testclient import TestClient


@pytest.mark.parametrize("text,age,budget", [
    ("I'm nineteen. I have ten dollars. I need food.", 19, 10),
    ("Im nineteen. I have 10 dollars. I need food.", 19, 10),
    ("I am nineteen, I have 10 dollars", 19, 10),
    ("I’m twenty-one and have twenty five dollars for food.", 21, 25),
    ("I am seventy five years old. I have one hundred and ten dollars.", 75, 110),
    ("I’m\u00a0nineteen. I have $10.50.", 19, 10.5),
    ("I'm twenty. I have a hundred dollars.", 20, 100),
    ("I am sixty and have a thousand dollars.", 60, 1000),
    ("I'm hungry and need food.", None, None),
])
def test_spoken_details_without_llm(monkeypatch, text, age, budget):
    monkeypatch.setattr(llm, "extract", lambda _: None)
    result = TestClient(app).post("/extract", json={"text": text})
    assert result.status_code == 200
    details = result.json()["constraints"]
    assert details["age"] == age
    assert details["budget_usd"] == budget


def test_fills_missing_llm_values_from_transcript(monkeypatch):
    monkeypatch.setattr(llm, "extract", lambda text: UserConstraints(
        needs=[Need(type=ServiceType.food)], constraints=Constraints(), raw_text=text,
        extraction_source="llm",
    ))
    result = extract("I'm nineteen, I have ten dollars. I have my ID. I need food.")
    assert result.constraints.age == 19
    assert result.constraints.budget_usd == 10
    assert result.constraints.has_id is True


def test_keeps_non_missing_llm_values(monkeypatch):
    monkeypatch.setattr(llm, "extract", lambda text: UserConstraints(
        needs=[Need(type=ServiceType.food)], constraints=Constraints(age=21, budget_usd=0), raw_text=text,
        extraction_source="llm",
    ))
    result = extract("I was nineteen with ten dollars. Now I'm twenty-one and broke.")
    assert result.constraints.age == 21
    assert result.constraints.budget_usd == 0


@pytest.mark.parametrize("text,children,other,size", [
    ("My two children need food with me.", True, False, 3),
    ("My partner and my two children need food with me.", True, True, 4),
    ("My partner needs food with me.", False, True, 2),
])
def test_household_flags_are_independent(text, children, other, size):
    result = fallback.extract(text).constraints
    assert result.children is children
    assert result.other_household_members is other
    assert result.family_size == size
