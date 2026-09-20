# AidGraph backend

FastAPI, Pydantic and NetworkX. Start with `../dev.sh` or:

```bash
uv venv .venv
uv pip install -e '.[dev]'
AIDGRAPH_DISABLE_LLM=1 .venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/python -m pytest -q
```

- `models.py`: resource, constraints, plan and strategy response contracts.
- `llm_client.py`: optional Gemini client; disabled by `AIDGRAPH_DISABLE_LLM`.
- `extraction/`: optional Gemini structured extraction and deterministic fallback.
- `planner/filters.py`: availability, capacity and eligibility checks.
- `planner/travel.py`: affordable walking, seeded bus, car and rideshare choices.
- `planner/graph.py`: travel and explanation graphs.
- `planner/search.py`: complete-route schedule, cumulative budget and deadline checks.
- `planner/service.py`: strategy comparison, duplicate collapse and replan diffs.
- `planner/timeline.py`: ordered call, travel and visit steps.
- `routers/plan.py`: `/extract`, reviewed-constraint `/plans`, and legacy endpoints.
- `routers/resources.py`: listing, status simulation and reset.
- `store.py`: dataset loading and local process memory for status changes and saved plans.

## Datasets

- `data/resources.json`: 12 sourced Baltimore organizations. Loaded by default.
- `data/resources.demo.json`: synthetic records with guaranteed demo coverage. Selected with `AIDGRAPH_DATASET=demo`; the test suite pins this set in `tests/conftest.py`.
- `data/transit.json`: approximate MTA CityLink routes shared by both datasets.

Availability changes are simulated and travel times are estimates. API docs: http://localhost:8000/docs. The root README covers the full workflow and limitations.
