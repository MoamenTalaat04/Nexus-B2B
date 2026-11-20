"""Egypt's 27 governorates and the main cities/districts (P1-2), for onboarding, settings and the ICP.

English names are what the app stores (business_settings.target_regions, leads.governorate); the Arabic labels
are for the UI. Names match app/core/geo_eg_coords.py, which holds the map centers used for search bias.
GET /api/v1/settings/geo returns this constant.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class City:
    name: str
    name_ar: str


@dataclass(frozen=True)
class GovernorateInfo:
    name: str
    name_ar: str
    cities: tuple[City, ...] = field(default_factory=tuple)


def _c(*pairs: tuple[str, str]) -> tuple[City, ...]:
    return tuple(City(en, ar) for en, ar in pairs)


GOVERNORATES: tuple[GovernorateInfo, ...] = (
    GovernorateInfo(
        "Cairo",
        "القاهرة",
        _c(
            ("Downtown", "وسط البلد"),
            ("Nasr City", "مدينة نصر"),
            ("Heliopolis", "مصر الجديدة"),
            ("Maadi", "المعادي"),
            ("Zamalek", "الزمالك"),
            ("Shubra", "شبرا"),
            ("New Cairo", "القاهرة الجديدة"),
            ("Mokattam", "المقطم"),
            ("Ain Shams", "عين شمس"),
            ("El Marg", "المرج"),
            ("Helwan", "حلوان"),
            ("El Matareya", "المطرية"),
            ("Abbassia", "العباسية"),
            ("El Mosky", "الموسكي"),
            ("Sayeda Zeinab", "السيدة زينب"),
            ("El Salam", "السلام"),
            ("Shorouk", "الشروق"),
            ("Madinaty", "مدينتي"),
        ),
    ),
    GovernorateInfo(
        "Giza",
        "الجيزة",
        _c(
            ("Dokki", "الدقي"),
            ("Mohandessin", "المهندسين"),
            ("Agouza", "العجوزة"),
            ("Haram", "الهرم"),
            ("Faisal", "فيصل"),
            ("Imbaba", "إمبابة"),
            ("Bulaq El Dakrour", "بولاق الدكرور"),
            ("6th of October", "السادس من أكتوبر"),
            ("Sheikh Zayed", "الشيخ زايد"),
            ("Hadayek El Ahram", "حدائق الأهرام"),
            ("Warraq", "الوراق"),
            ("Badrashin", "البدرشين"),
        ),
    ),
    GovernorateInfo(
        "Alexandria",
        "الإسكندرية",
        _c(
            ("Mansheya", "المنشية"),
            ("Smouha", "سموحة"),
            ("Miami", "ميامي"),
            ("Agami", "العجمي"),
            ("Borg El Arab", "برج العرب"),
            ("Sidi Gaber", "سيدي جابر"),
            ("Sporting", "سبورتنج"),
            ("Montaza", "المنتزه"),
            ("Moharam Bek", "محرم بك"),
            ("Amreya", "العامرية"),
            ("Raml Station", "محطة الرمل"),
        ),
    ),
    GovernorateInfo(
        "Qalyubia",
        "القليوبية",
        _c(
            ("Shubra El Kheima", "شبرا الخيمة"),
            ("Banha", "بنها"),
            ("Qalyub", "قليوب"),
            ("Obour", "العبور"),
            ("Khanka", "الخانكة"),
            ("Shibin El Qanater", "شبين القناطر"),
            ("Qanater El Khayreya", "القناطر الخيرية"),
        ),
    ),
    GovernorateInfo(
        "Sharqia",
        "الشرقية",
        _c(
            ("Zagazig", "الزقازيق"),
            ("10th of Ramadan", "العاشر من رمضان"),
            ("Belbeis", "بلبيس"),
            ("Minya El Qamh", "منيا القمح"),
            ("Abu Hammad", "أبو حماد"),
            ("Faqous", "فاقوس"),
            ("Hehya", "ههيا"),
        ),
    ),
    GovernorateInfo(
        "Dakahlia",
        "الدقهلية",
        _c(
            ("Mansoura", "المنصورة"),
            ("Talkha", "طلخا"),
            ("Mit Ghamr", "ميت غمر"),
            ("Aga", "أجا"),
            ("Sherbin", "شربين"),
            ("Belqas", "بلقاس"),
            ("El Manzala", "المنزلة"),
        ),
    ),
    GovernorateInfo(
        "Gharbia",
        "الغربية",
        _c(
            ("Tanta", "طنطا"),
            ("El Mahalla El Kubra", "المحلة الكبرى"),
            ("Kafr El Zayat", "كفر الزيات"),
            ("Zefta", "زفتى"),
            ("Samanoud", "سمنود"),
            ("Basyoun", "بسيون"),
        ),
    ),
    GovernorateInfo("Monufia", "المنوفية"),
    GovernorateInfo("Beheira", "البحيرة"),
    GovernorateInfo("Kafr El Sheikh", "كفر الشيخ"),
    GovernorateInfo("Damietta", "دمياط"),
    GovernorateInfo("Port Said", "بورسعيد"),
    GovernorateInfo("Ismailia", "الإسماعيلية"),
    GovernorateInfo("Suez", "السويس"),
    GovernorateInfo("North Sinai", "شمال سيناء"),
    GovernorateInfo("South Sinai", "جنوب سيناء"),
    GovernorateInfo("Red Sea", "البحر الأحمر"),
    GovernorateInfo("Matrouh", "مطروح"),
    GovernorateInfo("New Valley", "الوادي الجديد"),
    GovernorateInfo("Faiyum", "الفيوم"),
    GovernorateInfo("Beni Suef", "بني سويف"),
    GovernorateInfo("Minya", "المنيا"),
    GovernorateInfo("Asyut", "أسيوط"),
    GovernorateInfo("Sohag", "سوهاج"),
    GovernorateInfo("Qena", "قنا"),
    GovernorateInfo("Luxor", "الأقصر"),
    GovernorateInfo("Aswan", "أسوان"),
)

BY_NAME: dict[str, GovernorateInfo] = {g.name: g for g in GOVERNORATES}
GOVERNORATE_NAMES: tuple[str, ...] = tuple(BY_NAME)


def get_governorate(name: str) -> GovernorateInfo | None:
    """Exact English name, case-insensitive ("cairo" → Cairo)."""
    wanted = name.strip().casefold()
    return next((g for g in GOVERNORATES if g.name.casefold() == wanted), None)


def canonical_city(governorate: GovernorateInfo, city: str) -> str | None:
    """The listed city's English name for an English or Arabic spelling, or None if it is not listed."""
    wanted = city.strip().casefold()
    for c in governorate.cities:
        if wanted in (c.name.casefold(), c.name_ar):
            return c.name
    return None


def as_json() -> list[dict[str, object]]:
    return [
        {
            "name": g.name,
            "name_ar": g.name_ar,
            "cities": [{"name": c.name, "name_ar": c.name_ar} for c in g.cities],
        }
        for g in GOVERNORATES
    ]
