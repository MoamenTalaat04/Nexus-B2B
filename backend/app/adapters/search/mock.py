"""Deterministic Egyptian business search for tests and local development."""

import hashlib
from typing import Any

from app.adapters.base import PlaceResult, RegionFilter


class MockSearchSource:
    name = "mock_search"

    _CATEGORIES = (
        ("kids_clothing", "متجر ملابس أطفال", "Kids Clothing Store", "clothing_store"),
        ("clothing", "متجر ملابس", "Clothing Store", "clothing_store"),
        ("restaurant", "مطعم تجريبي", "Demo Restaurant", "restaurant"),
        ("pharmacy", "صيدلية تجريبية", "Demo Pharmacy", "pharmacy"),
    )

    async def search(
        self,
        query: str,
        *,
        region: RegionFilter,
        max_results: int = 20,
    ) -> list[PlaceResult]:
        count = min(max(max_results, 0), 20)
        seed = int(hashlib.sha256(f"{query}|{region.model_dump_json()}".encode()).hexdigest()[:8], 16)
        city = region.cities[0] if region.cities else region.governorate
        governorate = region.governorate or "Cairo"

        results: list[PlaceResult] = []
        for index in range(count):
            category_key, arabic_name, english_name, place_type = self._CATEGORIES[
                (seed + index) % len(self._CATEGORIES)
            ]
            suffix = (seed + index * 7919) % 100000000
            prefix = ("10", "11", "12", "15")[(seed + index) % 4]
            national = f"0{prefix}{suffix:08d}"
            international = f"+20{prefix}{suffix:08d}"
            has_phone = (seed + index) % 3 != 0
            has_website = (seed + index) % 4 != 0
            closed = (seed + index) % 11 == 0
            phone = international if has_phone else None
            raw: dict[str, Any] = {
                "mock": True,
                "category_key": category_key,
                "query": query,
                "phone_national": national,
            }
            results.append(
                PlaceResult(
                    source=self.name,
                    source_ref=f"mock-place-{seed}-{index}",
                    name=f"{arabic_name} — {english_name}",
                    category=place_type,
                    address=f"{city}، {governorate}",
                    city=city,
                    governorate=governorate,
                    lat=30.0 + ((seed + index) % 50) / 1000,
                    lng=31.0 + ((seed + index * 3) % 50) / 1000,
                    phone_national=national if has_phone else None,
                    phone_international=phone,
                    website=f"https://{english_name.lower().replace(' ', '-')}.example.com"
                    if has_website
                    else None,
                    google_maps_url=f"https://maps.example.com/place/mock-place-{seed}-{index}",
                    rating=round(3.5 + ((seed + index) % 15) / 10, 1),
                    reviews_count=(seed + index * 17) % 500,
                    business_status="CLOSED_PERMANENTLY" if closed else "OPERATIONAL",
                    types=[place_type],
                    raw=raw,
                )
            )
        return results
