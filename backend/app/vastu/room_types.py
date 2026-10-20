"""Canonical room-type vocabulary. Rules refer to these types, never to free-text labels."""
import re

ROOM_TYPES: dict[str, str] = {
    "living": "Living room",
    "kitchen": "Kitchen",
    "master_bedroom": "Master bedroom",
    "bedroom": "Bedroom",
    "toilet": "Toilet / bathroom",
    "pooja": "Pooja room",
    "dining": "Dining",
    "study": "Study",
    "staircase": "Staircase",
    "store": "Store room",
    "balcony": "Balcony",
    "utility": "Utility",
    "foyer": "Foyer / passage",
    "parking": "Parking",
    "other": "Other",
}

_SYNONYMS = [
    ("master_bedroom", r"master|mbr|m\.?\s*bed|main bed"),
    ("toilet", r"toilet|bath|wc|w\.c|washroom|lavatory|powder"),
    ("pooja", r"pooja|puja|prayer|mandir|temple|devghar"),
    ("kitchen", r"kitchen|kit\b|pantry"),
    ("bedroom", r"bed|br\b|guest|kids|children"),
    ("living", r"living|hall|drawing|lounge|family"),
    ("dining", r"dining|dinning"),
    ("study", r"study|office|library|work"),
    ("staircase", r"stair|steps"),
    ("store", r"store|storage|closet"),
    ("balcony", r"balcony|verandah|veranda|terrace|deck"),
    ("utility", r"utility|laundry|wash area|dry"),
    ("foyer", r"foyer|passage|lobby|corridor|entry"),
    ("parking", r"parking|garage|car"),
]


def infer_room_type(label: str) -> str:
    text = (label or "").lower()
    for room_type, pattern in _SYNONYMS:
        if re.search(pattern, text):
            return room_type
    return "other"


def normalise_room_type(room_type: str | None, label: str) -> str:
    return room_type if room_type in ROOM_TYPES else infer_room_type(label)
