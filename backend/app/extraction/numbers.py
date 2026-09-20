import re

UNITS = dict(zip(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(),
    range(20),
))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
WORDS = "|".join([*UNITS, *TENS, "hundred", "thousand"])
NUMBER = rf"(?:\d[\d,]*(?:\.\d+)?|(?:{WORDS})(?:[\s-]+(?:{WORDS}|and))*)"
AGE = re.compile(rf"\b(?:i'?m|i am|age|aged)\s+({NUMBER})\b|\b({NUMBER})\s+(?:years? old|yo|y/o)\b", re.I)
MONEY = re.compile(rf"\$\s*(-?\d[\d,]*(?:\.\d+)?)|(?<![\w.-])(-?{NUMBER})\s+(?:dollars?|bucks?)\b", re.I)


def number_value(value: str) -> float:
    value = value.lower().replace(",", "")
    if value.startswith("-"):
        return -number_value(value[1:])
    try:
        return float(value)
    except ValueError:
        total = current = 0
        for word in re.split(r"[\s-]+", value):
            if word in UNITS:
                current += UNITS[word]
            elif word in TENS:
                current += TENS[word]
            elif word == "hundred":
                current = (current or 1) * 100
            elif word == "thousand":
                total += (current or 1) * 1000
                current = 0
        return float(total + current)


def stated_number(pattern: re.Pattern, text: str) -> float | None:
    match = pattern.search(text)
    return number_value(match.group(1) or match.group(2)) if match else None
