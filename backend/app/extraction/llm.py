from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from ..llm_client import generate, generation_config, get_client
from ..models import Constraints, Need, ServiceType, UserConstraints


class ExtractedNeed(BaseModel):
    type: Literal["emergency_housing", "food", "long_term_assistance"]
    priority: Literal["high", "medium", "low"]
    deadline: Literal["tonight", "tomorrow", "this_week"]


class Extraction(BaseModel):
    needs: list[ExtractedNeed] = Field(description="Every need the person expressed or clearly implied.")
    age: Optional[int] = Field(default=None, description="Age in years if stated, else null.")
    budget_usd: Optional[float] = Field(default=None, description="Money available in USD if stated, else null.")
    has_car: bool = Field(default=False, description="True only if they clearly have a car they can use.")
    has_id: Optional[bool] = Field(default=None, description="True/false only if they said so; otherwise null.")
    family_size: int = Field(default=1, description="Number of people who need help together, including the speaker.")
    gender: Optional[Literal["male", "female"]] = Field(default=None, description="Only if clearly stated; otherwise null.")


SYSTEM = """You extract structured needs and constraints from a short description written by or for a person seeking community assistance.

Rules:
- Output only the fields in the schema. Do not invent facts. Unknown means null.
- Needs: emergency_housing = needs a place to sleep soon. food = hungry / no food. long_term_assistance = wants stable housing, benefits, rent help, case management, ID replacement.
- If someone lost their housing or has nowhere to sleep, add emergency_housing (priority high, deadline tonight) AND long_term_assistance (priority low, deadline this_week).
- 'tonight' means they need it within hours. 'tomorrow' for next-day. 'this_week' otherwise.
- has_car is false unless they clearly have a working car available.
- family_size counts everyone travelling together (e.g. 'me and my two kids' = 3).
- Do not name or recommend any organization. You only describe the person's situation."""

EXAMPLES = [
    ("I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight.",
     '{"needs":[{"type":"emergency_housing","priority":"high","deadline":"tonight"},{"type":"long_term_assistance","priority":"low","deadline":"this_week"}],"age":19,"budget_usd":10,"has_car":false,"has_id":null,"family_size":1,"gender":null}'),
    ("My friend needs somewhere to stay tonight, doesn't have a car, and hasn't eaten today.",
     '{"needs":[{"type":"emergency_housing","priority":"high","deadline":"tonight"},{"type":"food","priority":"high","deadline":"tonight"},{"type":"long_term_assistance","priority":"low","deadline":"this_week"}],"age":null,"budget_usd":null,"has_car":false,"has_id":null,"family_size":1,"gender":null}'),
]


def _to_constraints(x: Extraction, text: str) -> UserConstraints:
    needs = [Need(type=ServiceType(n.type), priority=n.priority, deadline=n.deadline) for n in x.needs]
    seen, uniq = set(), []
    for n in needs:
        if n.type not in seen:
            uniq.append(n)
            seen.add(n.type)
    return UserConstraints(
        needs=uniq,
        constraints=Constraints(age=x.age, budget_usd=x.budget_usd, has_car=x.has_car, has_id=x.has_id,
                                family_size=max(1, x.family_size), gender=x.gender),
        raw_text=text,
        extraction_source="llm",
    )


def _contents(text: str) -> list[dict]:
    contents: list[dict] = []
    for q, a in EXAMPLES:
        contents.append({"role": "user", "parts": [{"text": q}]})
        contents.append({"role": "model", "parts": [{"text": a}]})
    contents.append({"role": "user", "parts": [{"text": text}]})
    return contents


def extract(text: str) -> Optional[UserConstraints]:
    client = get_client()
    if client is None:
        return None
    try:
        resp = generate(
            _contents(text),
            generation_config(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_schema=Extraction,
            ),
        )
        if resp is None:
            return None
        parsed = resp.parsed
        if parsed is None:
            return None
        if not isinstance(parsed, Extraction):
            parsed = Extraction.model_validate(parsed)
        return _to_constraints(parsed, text)
    except Exception:
        return None
