from __future__ import annotations

import re

from ..models import Constraints, LatLng, Need, ServiceType, UserConstraints

HOUSING = re.compile(r"\b(nowhere to (stay|sleep|go)|no ?where to stay|place to (stay|sleep)|somewhere to (stay|sleep)|"
                     r"shelter|homeless|lost my (housing|apartment|home|place)|evicted|kicked out|sleep tonight|"
                     r"stay tonight|on the street|sleeping (outside|in my car|rough))\b", re.I)
FOOD = re.compile(r"\b(hungry|(?:haven'?t|hasn'?t|havent|hasnt|not|no)\s+(?:\w+\s+)?eaten|nothing to eat|food|meal|dinner|breakfast|eat|starving|pantry)\b", re.I)
LONG_TERM = re.compile(r"\b(long[- ]?term|permanent|apartment|rent|housing assistance|voucher|case ?manager|"
                       r"get back on my feet|job|benefits|application)\b", re.I)
NO_CAR = re.compile(r"\b(no car|(?:don'?t|doesn'?t|do not|does not|dont|doesnt) have (?:a |any )?(?:car|vehicle|ride)|"
                    r"without a car|no vehicle|no ride|can'?t drive|no transportation|don'?t drive|on foot|by bus|lost (?:my|the) car)\b", re.I)
HAS_CAR = re.compile(r"\b(have a car|my car|i can drive|i drive)\b", re.I)
NO_ID = re.compile(r"\b(no id|don'?t have (an |my )?id|lost my (id|wallet|license)|no identification|without id)\b", re.I)
HAS_ID = re.compile(r"\b(have (my|an|a photo|photo) id|have my license|got my id)\b", re.I)
AGE = re.compile(r"\b(?:i'?m|i am|age|aged)\s*(\d{1,3})\b|\b(\d{1,3})\s*(?:years? old|yo|y/o)\b", re.I)
MONEY = re.compile(r"\$\s?(-?\d[\d,]*(?:\.\d+)?)|(-?\d[\d,]*(?:\.\d+)?)\s*(?:dollars|bucks)", re.I)
NO_MONEY = re.compile(r"\b(no money|broke|nothing in my pocket|no cash|can'?t afford anything)\b", re.I)
FAMILY = re.compile(r"\b(my (?:\w+ )?(kids?|children|son|daughter|baby|wife|husband|partner|family))\b", re.I)
KIDS_COUNT = re.compile(r"\b(\d|one|two|three|four|five)\s*(kids?|children)\b", re.I)
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
FEMALE = re.compile(r"\b(i'?m a (woman|girl|mother|mom)|my husband|pregnant)\b", re.I)
MALE = re.compile(r"\b(i'?m a (man|guy|father|dad)|my wife)\b", re.I)
TOMORROW = re.compile(r"\b(tomorrow|next week|this week|later)\b", re.I)

NEIGHBORHOODS = {
    "Lexington Market": (39.291, -76.6215),
    "Mount Vernon": (39.2975, -76.615),
    "Charles Village": (39.32, -76.616),
    "Patterson Park": (39.2935, -76.581),
    "Federal Hill": (39.279, -76.611),
    "Brooklyn": (39.24, -76.605),
}


def extract(text: str) -> UserConstraints:
    t = text.strip().replace("’", "'")
    needs: list[Need] = []

    if HOUSING.search(t):
        needs.append(Need(type=ServiceType.emergency_housing, priority="high", deadline="tonight"))
    if FOOD.search(t) or HOUSING.search(t):
        needs.append(Need(type=ServiceType.food, priority="high", deadline="tonight"))
    if LONG_TERM.search(t) or any(n.type == ServiceType.emergency_housing for n in needs):
        needs.append(Need(type=ServiceType.long_term_assistance, priority="low", deadline="tomorrow"))
    if not needs:
        needs = [Need(type=ServiceType.emergency_housing, priority="high", deadline="tonight"),
                 Need(type=ServiceType.food, priority="medium", deadline="tonight")]

    age = None
    m = AGE.search(t)
    if m:
        age = int(m.group(1) or m.group(2))

    budget = None
    m = MONEY.search(t)
    if m:
        budget = float((m.group(1) or m.group(2)).replace(",", ""))
    elif NO_MONEY.search(t):
        budget = 0.0

    has_car = False
    if HAS_CAR.search(t) and not NO_CAR.search(t):
        has_car = True

    has_id = None
    if NO_ID.search(t) or re.search(r"(?:no|without|don't have (?:a |my )?)photo id|id (?:is )?(?:unavailable|missing)", t, re.I):
        has_id = False
    elif HAS_ID.search(t):
        has_id = True

    no_children = bool(re.search(r"\b(?:no|without|don't have(?: any)?|do not have(?: any)?) (?:kids?|children)\b", t, re.I))
    children = bool(re.search(r"\b(?:kids?|children|son|daughter|baby)\b", t, re.I)) and not no_children
    partner = bool(re.search(r"\bmy (?:wife|husband|partner)\b", t, re.I))
    family_size = 1 + int(partner)
    if children:
        m = KIDS_COUNT.search(t)
        n = m.group(1).lower() if m else "one"
        family_size += WORD_NUM[n] if n in WORD_NUM else int(n)
    elif not no_children and FAMILY.search(t):
        family_size = max(family_size, 2)

    transport = "own_vehicle" if has_car else "no_vehicle"
    if re.search(r"walking only|walk only|only walk|on foot", t, re.I):
        transport = "walking"
    elif re.search(r"public transit|bus only|by bus", t, re.I):
        transport = "public_transit"
    elif re.search(r"rideshare|uber|lyft", t, re.I):
        transport = "rideshare"

    accessibility = []
    if re.search(r"wheelchair|step.free", t, re.I):
        accessibility.append("step_free")
    if re.search(r"limited walking|can'?t walk far|cannot walk far", t, re.I):
        accessibility.append("limited_walking")
    if re.search(r"deaf|hearing support|hard of hearing", t, re.I):
        accessibility.append("hearing_support")

    pets = bool(re.search(r"(?:my|a|our) (?:pet|dog|cat)\b", t, re.I)) and not bool(re.search(r"no pets|without pets", t, re.I))

    deadline = "tonight"
    if re.search(r"within 24 hours|next 24 hours", t, re.I):
        deadline = "within_24_hours"
    elif re.search(r"this week|next week", t, re.I):
        deadline = "this_week"
    elif re.search(r"tomorrow", t, re.I) and not re.search(r"tonight", t, re.I):
        deadline = "tomorrow"
    explicit_deadline = bool(re.search(r"tonight|tomorrow|this week|next week|(?:within|next) 24 hours", t, re.I))
    has_housing = any(n.type == ServiceType.emergency_housing for n in needs)
    for need in needs:
        if need.type != ServiceType.long_term_assistance or (explicit_deadline and not has_housing):
            need.deadline = deadline

    label = next((name for name in NEIGHBORHOODS if name.lower() in t.lower()), "Lexington Market")
    lat, lng = NEIGHBORHOODS[label]
    gender = "female" if FEMALE.search(t) else ("male" if MALE.search(t) else None)

    return UserConstraints(
        needs=needs,
        constraints=Constraints(age=age, budget_usd=budget, has_car=has_car, has_id=has_id,
                                family_size=family_size, gender=gender, children=children, pets=pets,
                                accessibility=accessibility, transport=transport, transportation_needed=not has_car,
                                location_label=label, current_location=LatLng(lat=lat, lng=lng)),
        raw_text=t,
        extraction_source="fallback",
    )
