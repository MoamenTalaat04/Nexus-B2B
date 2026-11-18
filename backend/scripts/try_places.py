"""Manual check of the Google Places key and data (P2-1). Makes real, billable API calls.

    cd backend
    uv run python -m scripts.try_places "kids clothing shop" --governorate Cairo
    uv run python -m scripts.try_places "محل ملابس اطفال" --governorate Cairo --city "Nasr City" --max 20

Needs GOOGLE_PLACES_API_KEY in .env. Prints one line per result (name, area, phone/website flags, rating).
"""

import argparse
import asyncio
import sys

from app.adapters.base import RegionFilter
from app.adapters.search.google_places import GooglePlacesError, GooglePlacesSource


async def main() -> int:
    parser = argparse.ArgumentParser(description="Search Google Places (real API call).")
    parser.add_argument("query")
    parser.add_argument("--governorate", default="Cairo")
    parser.add_argument("--city", action="append", default=[], help="repeat for several cities")
    parser.add_argument("--max", type=int, default=20)
    args = parser.parse_args()

    try:
        source = GooglePlacesSource()
        places = await source.search(
            args.query,
            region=RegionFilter(governorate=args.governorate, cities=args.city),
            max_results=args.max,
        )
    except GooglePlacesError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for i, p in enumerate(places, 1):
        flags = ("📞" if p.phone_national or p.phone_international else "  ") + ("🌐" if p.website else "  ")
        rating = f"{p.rating:.1f}★ ({p.reviews_count})" if p.rating is not None else "no rating"
        closed = "" if p.business_status in (None, "OPERATIONAL") else f" [{p.business_status}]"
        print(f"{i:2}. {flags} {p.name} | {p.city or '-'}, {p.governorate} | {rating}{closed}")
    print(f"\n{len(places)} results, {source.last_request_count} billable request(s).")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Arabic names on the Windows console
    sys.exit(asyncio.run(main()))
