"""Approximate centers of Egypt's 27 governorates and main cities, for Google Places `locationBias` (P2-1).

These are a *bias*, not a filter: Google still returns places outside the circle, so a few kilometres of
error do not matter. Values are approximate city-center coordinates from public map data (not a surveyed
source); check a point on Google Maps if one ever looks wrong. Radii stay within the API limit of 50 km.

Names use the English governorate names of app/core/geo_eg.py (P1-2) plus the common Arabic names, so a
place's Arabic address (languageCode "ar") can be mapped back to the English governorate the app uses.
"""

import re
from dataclasses import dataclass, field

MAX_RADIUS_M = 50_000  # Places API (New) locationBias circle limit


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float
    radius_m: int


@dataclass(frozen=True)
class Governorate:
    name: str  # English, as stored in business_settings.target_regions
    name_ar: str
    center: Point
    cities: dict[str, Point] = field(default_factory=dict)


def _p(lat: float, lng: float, radius_km: float) -> Point:
    return Point(lat, lng, int(radius_km * 1000))


GOVERNORATES: dict[str, Governorate] = {
    g.name: g
    for g in [
        Governorate(
            "Cairo",
            "القاهرة",
            _p(30.0444, 31.2357, 25),
            {
                "Downtown": _p(30.0478, 31.2336, 4),
                "Nasr City": _p(30.0566, 31.3301, 6),
                "Heliopolis": _p(30.0911, 31.3225, 5),
                "Maadi": _p(29.9602, 31.2569, 5),
                "Zamalek": _p(30.0609, 31.2197, 2),
                "Shubra": _p(30.0838, 31.2445, 4),
                "New Cairo": _p(30.0074, 31.4913, 10),
                "Mokattam": _p(30.0213, 31.2925, 4),
                "Ain Shams": _p(30.1311, 31.3283, 4),
            },
        ),
        Governorate(
            "Giza",
            "الجيزة",
            _p(30.0131, 31.2089, 25),
            {
                "Dokki": _p(30.0384, 31.2120, 3),
                "Mohandessin": _p(30.0566, 31.2006, 3),
                "Haram": _p(29.9870, 31.1800, 5),
                "Faisal": _p(30.0071, 31.1758, 4),
                "Imbaba": _p(30.0760, 31.2090, 4),
                "6th of October": _p(29.9737, 30.9497, 12),
                "Sheikh Zayed": _p(30.0400, 30.9800, 8),
            },
        ),
        Governorate(
            "Alexandria",
            "الإسكندرية",
            _p(31.2001, 29.9187, 25),
            {
                "Mansheya": _p(31.1975, 29.8925, 3),
                "Smouha": _p(31.2156, 29.9424, 3),
                "Miami": _p(31.2681, 30.0063, 3),
                "Agami": _p(31.0960, 29.7570, 6),
                "Borg El Arab": _p(30.9180, 29.5370, 10),
            },
        ),
        Governorate(
            "Qalyubia",
            "القليوبية",
            _p(30.4660, 31.1848, 35),
            {
                "Shubra El Kheima": _p(30.1286, 31.2422, 6),
                "Banha": _p(30.4660, 31.1848, 6),
                "Qalyub": _p(30.1797, 31.2056, 5),
                "Obour": _p(30.1950, 31.4600, 8),
            },
        ),
        Governorate(
            "Sharqia",
            "الشرقية",
            _p(30.5877, 31.5020, 35),
            {
                "Zagazig": _p(30.5877, 31.5020, 7),
                "10th of Ramadan": _p(30.3060, 31.7420, 12),
                "Belbeis": _p(30.4205, 31.5629, 5),
            },
        ),
        Governorate(
            "Dakahlia",
            "الدقهلية",
            _p(31.0409, 31.3785, 35),
            {
                "Mansoura": _p(31.0409, 31.3785, 7),
                "Talkha": _p(31.0535, 31.3779, 4),
                "Mit Ghamr": _p(30.7167, 31.2597, 5),
            },
        ),
        Governorate(
            "Gharbia",
            "الغربية",
            _p(30.7865, 31.0004, 30),
            {
                "Tanta": _p(30.7865, 31.0004, 7),
                "El Mahalla El Kubra": _p(30.9697, 31.1669, 7),
                "Kafr El Zayat": _p(30.8247, 30.8152, 5),
            },
        ),
        Governorate("Monufia", "المنوفية", _p(30.5594, 31.0110, 30)),
        Governorate("Beheira", "البحيرة", _p(31.0341, 30.4682, 40)),
        Governorate("Kafr El Sheikh", "كفر الشيخ", _p(31.1107, 30.9388, 35)),
        Governorate("Damietta", "دمياط", _p(31.4165, 31.8133, 25)),
        Governorate("Port Said", "بورسعيد", _p(31.2653, 32.3019, 20)),
        Governorate("Ismailia", "الإسماعيلية", _p(30.5965, 32.2715, 25)),
        Governorate("Suez", "السويس", _p(29.9668, 32.5498, 25)),
        Governorate("North Sinai", "شمال سيناء", _p(31.1316, 33.7984, 40)),
        Governorate("South Sinai", "جنوب سيناء", _p(27.9158, 34.3299, 50)),
        Governorate("Red Sea", "البحر الأحمر", _p(27.2579, 33.8116, 40)),
        Governorate("Matrouh", "مطروح", _p(31.3543, 27.2373, 40)),
        Governorate("New Valley", "الوادي الجديد", _p(25.4390, 30.5586, 50)),
        Governorate("Faiyum", "الفيوم", _p(29.3084, 30.8428, 30)),
        Governorate("Beni Suef", "بني سويف", _p(29.0661, 31.0994, 30)),
        Governorate("Minya", "المنيا", _p(28.0871, 30.7618, 35)),
        Governorate("Asyut", "أسيوط", _p(27.1783, 31.1859, 35)),
        Governorate("Sohag", "سوهاج", _p(26.5591, 31.6957, 35)),
        Governorate("Qena", "قنا", _p(26.1551, 32.7160, 35)),
        Governorate("Luxor", "الأقصر", _p(25.6872, 32.6396, 25)),
        Governorate("Aswan", "أسوان", _p(24.0889, 32.8998, 30)),
    ]
}

# ---------------------------------------------------------------------------------------------- lookups

_ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_PREFIXES = ("محافظه ", "governorate of ")  # already normalized (ة → ه)
_SUFFIX = " governorate"


def normalize_arabic(text: str) -> str:
    """Lowercase, no diacritics or tatweel, alef/taa marbuta/yaa variants unified, single spaces."""
    s = _ARABIC_DIACRITICS.sub("", text.strip().lower()).replace("ـ", "")
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return " ".join(s.split())


def normalize_name(text: str) -> str:
    """normalize_arabic + dashes as spaces + 'Governorate' / 'محافظة' removed (place-name matching)."""
    s = normalize_arabic(text.replace("-", " "))
    for prefix in _PREFIXES:
        s = s.removeprefix(prefix)
    s = s.removesuffix(_SUFFIX)
    return s.replace("al ", "el ").strip()


_BY_NAME: dict[str, Governorate] = {}
for _g in GOVERNORATES.values():
    _BY_NAME[normalize_name(_g.name)] = _g
    _BY_NAME[normalize_name(_g.name_ar)] = _g


def find_governorate(name: str | None) -> Governorate | None:
    """The governorate for an English or Arabic name ("Giza", "محافظة الجيزة", "Giza Governorate")."""
    if not name:
        return None
    return _BY_NAME.get(normalize_name(name))


def find_city(governorate: Governorate, city: str | None) -> Point | None:
    if not city:
        return None
    wanted = normalize_name(city)
    for name, point in governorate.cities.items():
        if normalize_name(name) == wanted:
            return point
    return None
