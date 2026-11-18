"""Where business code gets external-system adapters (CONTRACTS section 7). Never import a concrete adapter.

How to add an adapter: put the module next to its siblings (e.g. app/adapters/search/<name>.py) with a
class that implements the Protocol from app/adapters/base.py, then map its name in the matching getter
below. Real adapters are imported lazily, so a missing module only fails when it is actually used.

Stand-in written in P2-1 with only get_search_source. P0-1 owns this file and adds the mocks plus
get_enrichers / get_channel / get_notifier.
"""

import importlib

from app.adapters.base import SearchSource
from app.config import settings

# name → (module, class, the task that adds it)
_SEARCH_SOURCES = {
    "google_places": ("app.adapters.search.google_places", "GooglePlacesSource", "P2-1"),
}
_MOCK_SEARCH = ("app.adapters.search.mock", "MockSearchSource", "P0-1")


def _load(module_name: str, class_name: str, task: str) -> type:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        raise NotImplementedError(f"{module_name} does not exist yet; it is added in {task}.") from exc
    cls: type = getattr(module, class_name)
    return cls


def get_search_source(name: str = "google_places") -> SearchSource:
    """The search source `name`, or the mock when USE_MOCK_ADAPTERS=true."""
    if settings.USE_MOCK_ADAPTERS:
        source: SearchSource = _load(*_MOCK_SEARCH)()
        return source
    if name not in _SEARCH_SOURCES:
        raise ValueError(f"Unknown search source {name!r}. Known: {', '.join(_SEARCH_SOURCES)}.")
    source = _load(*_SEARCH_SOURCES[name])()
    return source
