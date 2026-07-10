# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Google Maps Geocoding service for delivery points."""

import logging
from dataclasses import dataclass
from decimal import Decimal

import requests

from django_deliverypoints import settings as dp_settings

logger = logging.getLogger(__name__)


@dataclass
class GeocodingResult:
    latitude: Decimal
    longitude: Decimal
    formatted_address: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    post_code: str = ""
    country: str = ""  # ISO 3166-1 alpha-2


def _get_api_key() -> str:
    return dp_settings.GOOGLE_GEOCODING_API_KEY


def is_available() -> bool:
    """Check if geocoding is configured."""
    return bool(_get_api_key())


def _parse_address_components(components: list[dict]) -> dict:
    """Extract structured address from Google's address_components."""
    mapping = {
        "street_number": "street_number",
        "route": "route",
        "locality": "city",
        "administrative_area_level_1": "state",
        "postal_code": "post_code",
        "country": "country",
    }
    result = {}
    for comp in components:
        for comp_type in comp.get("types", []):
            if comp_type in mapping:
                key = mapping[comp_type]
                if key == "country":
                    result[key] = comp.get("short_name", "")
                else:
                    result[key] = comp.get("long_name", "")
    # Combine street_number + route into street
    street_parts = []
    if result.get("route"):
        street_parts.append(result["route"])
    if result.get("street_number"):
        street_parts.append(result["street_number"])
    result["street"] = " ".join(street_parts)
    result.pop("street_number", None)
    result.pop("route", None)
    return result


def _result_from_google(item: dict) -> GeocodingResult:
    """Convert a single Google Geocoding API result to GeocodingResult."""
    location = item.get("geometry", {}).get("location", {})
    parsed = _parse_address_components(item.get("address_components", []))
    return GeocodingResult(
        latitude=Decimal(str(location.get("lat", 0))),
        longitude=Decimal(str(location.get("lng", 0))),
        formatted_address=item.get("formatted_address", ""),
        street=parsed.get("street", ""),
        city=parsed.get("city", ""),
        state=parsed.get("state", ""),
        post_code=parsed.get("post_code", ""),
        country=parsed.get("country", ""),
    )


def geocode_address(
    street: str = "", city: str = "", post_code: str = "", country: str = "", state: str = ""
) -> GeocodingResult | None:
    """Geocode an address to coordinates.

    Returns GeocodingResult with lat/lng or None on failure.
    """
    api_key = _get_api_key()
    if not api_key:
        return None

    address_parts = [p for p in [street, city, state, post_code, country] if p]
    if not address_parts:
        return None

    address_string = ", ".join(address_parts)
    params = {"address": address_string, "key": api_key}

    try:
        resp = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        logger.warning("Geocoding request failed for address: %s", address_string)
        return None

    results = data.get("results", [])
    if not results:
        return None

    return _result_from_google(results[0])


def search_addresses(query: str, country_bias: str | None = None, limit: int = 5) -> list[GeocodingResult]:
    """Search for addresses matching a query string.

    Returns list of GeocodingResult candidates for CMS address lookup.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    if not query or len(query) < 3:
        return []

    params = {"address": query, "key": api_key}
    if country_bias:
        params["components"] = f"country:{country_bias}"

    try:
        resp = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        logger.warning("Geocoding search failed for query: %s", query)
        return []

    results = data.get("results", [])
    return [_result_from_google(item) for item in results[:limit]]
