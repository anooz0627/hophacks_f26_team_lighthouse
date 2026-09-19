# AidGraph Implementation Plan (HopHacks MVP)

> **Principle:** the LLM understands the situation; the planner (deterministic code) computes a plan that is actually feasible.
> The LLM never produces the plan itself. Every plan is derived from verified data and a deterministic algorithm.

---

## 0. Key Design Decisions

These settle the questions left open in the design document.

| Topic | Decision | Rationale |
|---|---|---|
| Data storage | **JSON file** (`backend/data/resources.json`) | A database is overkill for 20–30 resources. Load into server memory and handle status changes in memory. Supabase is a stretch goal. |
| Map | **Leaflet + OpenStreetMap** | No API key, free, minimal hackathon risk. Swap for Mapbox only if time allows. |
| Travel time | **Haversine straight-line estimate + fixed bus route table** | Integrating a live transit API is wasted time. Label all values as estimates in the UI. |
| Plan search | **Filter → exhaustive search over small candidate sets (small k) → scoring** | With this few resources, exhaustive search is simpler and easier to debug than Dijkstra/A*. NetworkX is used only for the travel graph and visualization. |
| LLM | **Structured JSON extraction only** + plan explanation text | A rule-based fallback parser guarantees the demo never dies on an LLM failure. |
| Replanning | **Status change → full recomputation with the same constraints → diff against the previous plan** | Full recomputation is simpler than partial edits and always correct. With ~30 resources it runs in milliseconds. |

---

## 1. Repository Layout

```
aid_graph/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point, CORS, router registration
│   │   ├── models.py            # Pydantic: Resource, UserConstraints, Plan, PlanStep
│   │   ├── data/
│   │   │   ├── resources.json   # 20–30 Baltimore resources
│   │   │   └── transit.json     # Bus routes (stop lists + headways)
│   │   ├── store.py             # JSON loading, in-memory availability state
│   │   ├── extraction/
│   │   │   ├── llm.py           # LLM call → UserConstraints JSON
│   │   │   └── fallback.py      # Regex/keyword backup parser
│   │   ├── planner/
│   │   │   ├── filters.py       # Hard filters: eligibility, cost, availability
│   │   │   ├── travel.py        # Distance, walking/bus time and cost
│   │   │   ├── graph.py         # NetworkX graph build (visualization + travel graph)
│   │   │   ├── search.py        # Candidate combination search + scoring
│   │   │   └── timeline.py      # Selected route → timestamped step list
│   │   ├── explain.py           # LLM-generated plan summary (template on failure)
│   │   └── routers/
│   │       ├── plan.py          # POST /plan, POST /replan
│   │       └── resources.py     # GET /resources, PATCH /resources/{id}/status
│   ├── tests/
│   │   ├── test_filters.py
│   │   ├── test_search.py
│   │   └── test_replan.py       # "Shelter A FULL → Shelter B selected" scenario
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Main screen (input + results)
│   │   └── admin/page.tsx       # Resource status toggle panel (demo)
│   ├── components/
│   │   ├── SituationInput.tsx
│   │   ├── ConstraintsPanel.tsx # Displays extracted needs/constraints
│   │   ├── Timeline.tsx
│   │   ├── PlanMap.tsx          # Leaflet (dynamic import, SSR disabled)
│   │   ├── ResourceGraph.tsx    # Simple node graph (optional)
│   │   └── ReplanBanner.tsx     # "Shelter A is now full; the plan has changed"
│   ├── lib/api.ts
│   └── lib/types.ts             # TypeScript types mirroring the backend models
├── hophacks_design.md
└── implementation_detail.md
```

---

## 2. Data Model

### 2.1 Resource (`resources.json`)

```json
{
  "id": "shelter_a",
  "name": "Example Emergency Shelter",
  "service": "emergency_housing",
  "description": "...",
  "address": "...",
  "lat": 39.29, "lng": -76.61,
  "phone": "410-000-0000",
  "hours": [
    { "days": ["mon","tue","wed","thu","fri","sat","sun"], "open": "18:00", "close": "08:00" }
  ],
  "intake_deadline": "20:00",
  "eligibility": {
    "min_age": 18, "max_age": null,
    "requires_id": true,
    "gender": null,
    "families_ok": false
  },
  "cost": 0,
  "capacity": 4,
  "status": "available",
  "source_url": "...",
  "notes": "Photo ID required at intake."
}
```

- `service` enum: `emergency_housing | food | transportation | long_term_assistance`
- `status` enum: `available | full | closed | unavailable | delayed`
- If `hours.close < open`, the window is interpreted as crossing midnight.
- Every resource carries a `source_url` so the UI can show that the data is verified (addresses the data-accuracy risk).

### 2.2 Transit (`transit.json`)

```json
{
  "routes": [
    { "id": "citylink_red", "name": "CityLink Red", "fare": 2.0, "headway_min": 15,
      "stops": [ { "name": "...", "lat": 39.3, "lng": -76.6 }, ... ] }
  ],
  "walk_speed_kmh": 4.5
}
```

### 2.3 UserConstraints (LLM output schema)

```json
{
  "needs": [
    { "type": "emergency_housing", "priority": "high", "deadline": "tonight" },
    { "type": "food", "priority": "high", "deadline": "tonight" },
    { "type": "long_term_assistance", "priority": "low", "deadline": "tomorrow" }
  ],
  "constraints": {
    "age": 19,
    "budget_usd": 10,
    "has_car": false,
    "has_id": null,
    "family_size": 1,
    "current_location": null,
    "start_time": "2026-09-17T18:00:00"
  },
  "raw_text": "..."
}
```

- When `has_id` is `null`, prefer resources that do not require ID and flag those that do with a warning.
- When `current_location` is absent, the frontend supplies a default (e.g. central Baltimore).
- `transportation` is treated as a **travel constraint**, not a need (`has_car=false` → walking and bus only).

### 2.4 Plan (API response)

```json
{
  "plan_id": "uuid",
  "constraints": { ...UserConstraints },
  "steps": [
    { "order": 1, "time": "18:10", "type": "call",   "resource_id": "shelter_a",
      "title": "Call Shelter A", "detail": "4 beds available. Photo ID required.",
      "lat": 39.29, "lng": -76.61 },
    { "order": 2, "time": "18:25", "type": "travel", "route_id": "citylink_red",
      "title": "Take CityLink Red", "detail": "22 min, $2.00",
      "polyline": [[lat,lng],...] },
    { "order": 3, "time": "19:00", "type": "visit",  "resource_id": "shelter_a", ... }
  ],
  "total_cost_usd": 2.0,
  "score": 0.83,
  "explanation": "Two- to three-sentence summary generated by the LLM",
  "rejected": [
    { "resource_id": "shelter_c", "reason": "intake closes 17:00, arrival 18:40" }
  ],
  "graph": { "nodes": [...], "edges": [...] }
}
```

- `rejected` shows judges *why* alternatives were not chosen; it is a key technical-depth signal.
- `graph` feeds the frontend resource graph visualization.

---

## 3. Backend Pipeline

```
POST /plan { text, current_location? }
  │
  ├─ 1. extraction.llm.extract(text) ──on failure──▶ extraction.fallback.extract(text)
  │        → UserConstraints
  │
  ├─ 2. planner.filters.apply(resources, constraints, now)
  │        → per-resource {eligible: bool, reason}
  │
  ├─ 3. planner.graph.build(eligible_resources, transit, origin)
  │        → NetworkX DiGraph (nodes = places, edges = travel time/cost)
  │
  ├─ 4. planner.search.best_path(graph, constraints)
  │        → ordered resource list + score
  │
  ├─ 5. planner.timeline.build(path, graph, start_time)
  │        → PlanStep list with timestamps
  │
  ├─ 6. explain.summarize(plan) ──on failure──▶ template sentence
  │
  └─ Plan response (includes constraints for reuse during replanning)
```

### 3.1 LLM extraction (`extraction/llm.py`)

- System prompt: "Respond only in the following JSON schema," followed by the schema and two few-shot examples.
- Use structured output / JSON mode. Validate the response with Pydantic; on failure, retry once, then fall back.
- Temperature 0. Timeout 8 seconds.
- **Never give the LLM resource names.** The LLM must not select resources.

### 3.2 Fallback parser (`extraction/fallback.py`)

- Regex rules: age (`\b(\d{1,2})\b` near "I'm" / "years old"), budget (`\$(\d+)`), car (`no car|don't have a car`), keywords → needs (`sleep|stay|shelter|housing` → emergency_housing, `eat|food|hungry` → food).
- Tests pin the three or four demo sentences so the fallback alone produces correct output. **This is the insurance policy for an expired API key or network failure during the demo.**

### 3.3 Hard filters (`planner/filters.py`)

Each resource is checked in order; the first failing rule is recorded as the reason:

1. `status != available` → "currently full/closed"
2. `service` not among the needs → excluded (no reason recorded)
3. `min_age > age` or `max_age < age` → "age requirement"
4. `requires_id and has_id == False` → "requires ID" (`None` passes but sets a `warning` flag)
5. `cost > budget` → "exceeds budget"
6. `families_ok == False and family_size > 1` → "no families"
7. **Time is not checked here.** Arrival time depends on the route, so it is validated in the search stage.

### 3.4 Travel estimation (`planner/travel.py`)

```python
def travel_options(a, b, constraints) -> list[TravelLeg]:
    # 1) Walking: dist_km / walk_speed → minutes. Cost 0. Excluded beyond 3 km.
    # 2) Bus: if the nearest stop to a and the nearest stop to b share a route,
    #         walk (to stop) + wait (headway/2) + ride (stop distance at 25 km/h) + walk.
    #         Cost = fare. Excluded if it exceeds the budget.
    # 3) Car (has_car=True): dist / 30 km/h, cost 0.
    # Return the fastest option (cheapest on ties).
```

- Sufficient for a hackathon. The UI labels every figure "Estimated".

### 3.5 Search and scoring (`planner/search.py`)

```
1. Sort needs by priority (high → low), then deadline (tonight → tomorrow).
2. For each need, keep only the k=4 filter-passing resources nearest the origin as candidates.
3. Generate every combination of candidates for "tonight" needs with itertools.product
   (4^3 = 64 combinations; negligible).
4. For each combination, iterate over visit-order permutations, with:
   - emergency_housing always last (the person sleeps there)
   - Simulation per combination: t = start_time; travel to each resource → compute arrival
     → check arrival is within hours and before intake_deadline (discard otherwise)
     → check cumulative cost ≤ budget
5. Score surviving combinations:
     score = 1.0
           - 0.3 * (total_travel_min / 120)
           - 0.2 * (total_cost / max(budget, 1))
           - 0.2 * (1 if any warning else 0)         # e.g. ID uncertainty
           + 0.1 * (slack_min / 60)                  # time remaining before deadline
   Return the highest-scoring combination. If none survive, drop needs one at a time and retry;
   if still none, return a partial plan plus the reasons it is infeasible.
6. "Tomorrow" needs are appended after the tonight plan as the single nearest candidate
   (hours check only).
```

- Score weights are module-level constants so they can be tuned during the demo.
- Reasons for discarded combinations are collected into `rejected` (one representative reason per resource).

### 3.6 Timeline (`planner/timeline.py`)

- Walk the route and emit `PlanStep`s of three types:
  - `call` — for shelters with a phone number, a "call ahead to confirm a bed" step is inserted automatically before departure
  - `travel` — leg details; the polyline is the concatenated stop coordinates
  - `visit` — arrival time and items to bring (e.g. "Photo ID" when `requires_id` is set)
- Times are emitted both as `HH:MM` and ISO 8601.

### 3.7 Replanning (`routers/plan.py`, `store.py`)

```
PATCH /resources/{id}/status { status: "full" }
  → applied to the in-memory store
  → response: the updated resource

POST /replan { plan_id }
  → retrieve the stored plan's constraints and rerun the /plan logic unchanged
  → response: { new_plan, diff: { removed_resource_ids, added_resource_ids, changed_steps } }
```

- The frontend calls `/replan` immediately after the PATCH (alternatively, the PATCH response could list affected plan IDs).
- Plans live in an in-memory dict `{plan_id: Plan}`. Losing them on restart is acceptable.
- The frontend uses `diff` to fade the previous route to grey and highlight the new one. **This is the main demo moment.**

### 3.8 Explanation (`explain.py`)

- Give the LLM **only the completed plan JSON** with the instruction: "Explain this plan warmly in two to three sentences. Do not add any information that is not in the plan."
- Fallback template: `"Tonight: {n} steps, arriving at {shelter} by {time}. Bring: {docs}."`

---

## 4. API Reference

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/plan` | `{ text, current_location?: {lat,lng}, now?: ISO }` | `Plan` |
| POST | `/replan` | `{ plan_id }` | `{ plan: Plan, diff }` |
| GET | `/resources` | – | `Resource[]` (map markers, admin panel) |
| PATCH | `/resources/{id}/status` | `{ status }` | `Resource` |
| POST | `/extract` | `{ text }` | `UserConstraints` (debug/demo: show extraction before planning) |
| GET | `/health` | – | `{ ok, llm: bool }` |

- `now` is required to pin the demo clock. The 6:00 PM scenario can be presented at any time of day.

---

## 5. Frontend

### 5.1 Layout (single page)

```
┌──────────────────────────────────────────────────────────┐
│  AidGraph                                    [Admin ⚙]   │
├───────────────────────┬──────────────────────────────────┤
│ Situation textarea    │                                  │
│ [Example buttons ×3]  │          Map (Leaflet)           │
│ [Generate plan]       │   Markers: you / shelter / food  │
├───────────────────────┤   Lines: route (color by type)   │
│ Extracted situation   │                                  │
│  Housing  HIGH        │                                  │
│  Food     HIGH        ├──────────────────────────────────┤
│  Budget   $10         │  Timeline                        │
│  Vehicle  None        │  18:10 📞 Call Shelter A         │
├───────────────────────┤  18:25 🚌 CityLink Red (22m)     │
│ Considered, excluded  │  19:00 🏠 Check in · Bring ID    │
│  Shelter C – closed   │  Tomorrow 09:00 🏢 Resource Ctr  │
│  Pantry D – budget    │                                  │
└───────────────────────┴──────────────────────────────────┘
```

### 5.2 State flow

```
idle → extracting  (POST /extract; animate the extraction result)
     → planning    (POST /plan)
     → planned     (render map + timeline)
     → replanning  (PATCH status → POST /replan → diff animation → planned)
```

- `/extract` is called separately first so the demo visibly shows "the LLM understood the situation." The extra one to two seconds is worth it.

### 5.3 Admin panel (`/admin` or side drawer)

- Lists `/resources` with a status dropdown; changes issue a PATCH.
- Must be reachable from the main screen without a tab switch (minimize screen changes during the pitch). A side drawer is recommended.
- Header text: "Simulated nonprofit updates" (addresses the data-accuracy risk).

### 5.4 Map

- `react-leaflet`, loaded with `next/dynamic` and SSR disabled.
- Marker colors keyed by service type. Only the selected route is drawn at full opacity; other resources are dimmed.
- On replan: keep the previous polyline as a grey dashed line for 1.5 s, then remove it.

---

## 6. Data Preparation (Data / AI owner)

- 20–30 resources based on real Baltimore organizations. Rough split: 8 shelters, 8 kitchens/pantries, 4 long-term assistance centers, 3–5 other.
- **Design the data so the demo scenario is guaranteed to work:**
  - Shelter A: accepts age 19, requires ID, intake 20:00, reachable by bus, closest → selected in the first plan
  - Shelter B: no ID required, slightly farther but reachable by bus → the alternative when A is full
  - Shelter C: intake closes 17:00 → appears in `rejected` (shows the filter working)
  - Shelter D: min_age 21 → rejected (age)
  - Kitchen X: dinner 17:00–19:00, located between A and B → can appear in both plans
- Two or three bus routes with five to eight stops each. Use real MTA route names; stop positions may be approximate.
- Every entry includes `source_url` and a last-verified date.

---

## 7. 36-Hour Timeline

### 0–6 h: Foundation
- [ ] Repository, FastAPI + Next.js scaffolds, CORS, `/health`
- [ ] Finalize `models.py` → mirror in `types.ts` (any later change updates both)
- [ ] First 10 entries in `resources.json` (the 5 demo-scenario resources first)
- [ ] `filters.py` + tests

### 6–14 h: Planner (most important)
- [ ] `travel.py`, `graph.py`, `search.py`, `timeline.py`
- [ ] `POST /plan` works with **hard-coded constraints** (no LLM)
- [ ] `test_replan.py`: A FULL → B selected
- [ ] Frontend: timeline component rendered from mock data

### 14–22 h: LLM + map
- [ ] `llm.py` + `fallback.py` + `/extract`
- [ ] Frontend: input → extraction panel → plan wired end to end
- [ ] Leaflet map with markers and polylines
- [ ] 25+ resource entries

### 22–30 h: Replanning + demo moment
- [ ] `PATCH status`, `/replan`, diff
- [ ] Admin drawer
- [ ] Replan animation (fade previous route, banner)
- [ ] `rejected` panel
- [ ] `explain.py`

### 30–36 h: Stabilization
- [ ] Pinned demo clock (`now` parameter), three example-sentence buttons
- [ ] Verify the full demo runs without an LLM key (fallback path)
- [ ] Three pitch rehearsals; fix only bugs that surface. No new features.
- [ ] README and screenshots

---

## 8. Team Roles (four people)

| Owner | Files | Deliverable by 14 h |
|---|---|---|
| Backend / Planner | `planner/*`, `routers/plan.py`, `tests/` | `/plan` response with hard-coded constraints |
| Data / AI | `data/*.json`, `extraction/*`, `explain.py` | 15 resources + working `/extract` |
| Frontend | `SituationInput`, `ConstraintsPanel`, `Timeline`, `ReplanBanner` | Timeline rendered from mock data |
| Map / Integration | `PlanMap`, `admin`, `lib/api.ts`, deployment | Map markers + backend connection |

- The interface contract is `models.py` / `types.ts`. All four agree on it within the first two hours; subsequent changes are announced in Slack.

---

## 9. Rules

**Always**
- Include `rejected` and `source_url` in every plan response (technical depth + trust).
- Label all times and distances as "Estimated".
- Keep the demo runnable end to end through the fallback when the LLM is unavailable.
- Replan by full recomputation. Never attempt partial edits.

**Never**
- Live transit APIs, Supabase, authentication, multilingual support, or voice before hour 30, and only then if the core is flawless.
- Give the LLM the resource list and ask it to choose.
- State eligibility definitively ("You qualify"). Use "Known requirements: ..." instead.

---

## 10. Demo Checklist

1. With the clock pinned to 18:00, click an example-sentence button.
2. The extraction panel shows Housing HIGH / Food HIGH / $10 / No car.
3. Timeline and map show Kitchen X → Bus → Shelter A.
4. The rejected panel lists Shelter C (intake closed) and Shelter D (age).
5. In the admin drawer, set Shelter A → FULL.
6. Banner: "Shelter A is now full. Replanning…" → new route via Shelter B, previous route fades.
7. Closing: "Resource directories tell people what help exists. AidGraph tells them how to actually reach it."
