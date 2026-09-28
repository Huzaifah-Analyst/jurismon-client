"""JurisMon Platform Adapters Registry & Factory."""

from typing import Dict, Any, Type
from crawler.adapters.base_adapter import BaseAdapter
from crawler.adapters.municode import MunicodeAdapter
from crawler.adapters.granicus import GranicusAdapter
from crawler.adapters.civicplus import CivicPlusAdapter
from crawler.adapters.custom import CustomAdapter
from crawler.adapters.rest_api import RestApiAdapter
from crawler.session import SafeHTTPSession

ADAPTER_MAP: Dict[str, Type[BaseAdapter]] = {
    "municode": MunicodeAdapter,
    "granicus": GranicusAdapter,
    "civicplus": CivicPlusAdapter,
    "custom": CustomAdapter,
    "rest_api": RestApiAdapter,
    "api": RestApiAdapter,
    "json": RestApiAdapter,
}


def get_adapter(adapter_type: str, session: SafeHTTPSession = None) -> BaseAdapter:
    """Returns an instantiated adapter for the specified municipal platform."""
    adapter_cls = ADAPTER_MAP.get(adapter_type.lower(), CustomAdapter)
    return adapter_cls(session=session)


__all__ = [
    "BaseAdapter",
    "MunicodeAdapter",
    "GranicusAdapter",
    "CivicPlusAdapter",
    "CustomAdapter",
    "get_adapter",
]
