# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""CSV import service for delivery points."""

import csv
import logging
from dataclasses import dataclass
from typing import IO

from django_deliverypoints.models import DeliveryPoint, DeliveryPointType, ImportLog
from django_deliverypoints.services import geocoding_service

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    disabled: int = 0
    geocoded: int = 0
    geocode_failed: int = 0
    warnings: int = 0


def _detect_changes(existing: DeliveryPoint, defaults: dict) -> list[str]:
    """Return list of field names that differ between existing point and new defaults."""
    changed = []
    for field_name, new_value in defaults.items():
        old_value = getattr(existing, field_name, None)
        if field_name in ("latitude", "longitude"):
            old_value = float(old_value) if old_value is not None else None
        if old_value != new_value:
            changed.append(field_name)
    return changed


def _try_geocode(row: dict) -> tuple[float | None, float | None, bool]:
    """Attempt to geocode from address fields. Returns (lat, lng, success)."""
    city = row.get("delivery-point-city", "")
    if not city:
        return None, None, False

    if not geocoding_service.is_available():
        return None, None, False

    result = geocoding_service.geocode_address(
        street=row.get("delivery-point-address", ""), city=city, post_code=row.get("delivery-point-postcode", "")
    )
    if result:
        return float(result.latitude), float(result.longitude), True
    return None, None, False


def import_csv(*, file: IO[str], type_code: str, mode: str, channel=None, source: str = "cli") -> ImportResult:
    """Import points from CSV file.

    Args:
        file: File-like object (StringIO or file handle) with CSV content.
        type_code: DeliveryPointType.code to import for.
        mode: "incremental" or "full".
        channel: Optional DeliveryPointChannel for channel-scoped imports.
        source: Origin of import ("cli" or "api").
    """
    reader = csv.DictReader(file)
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty or contains only a header row.")

    dp_type = DeliveryPointType.objects.get(code=type_code)
    result = ImportResult()
    imported_codes: set[str] = set()
    entries: list[dict] = []

    # Check if coordinate columns exist in header
    has_coords = "delivery-point-x" in rows[0] and "delivery-point-y" in rows[0]

    if not has_coords and not geocoding_service.is_available():
        logger.warning(
            "Geocoding skipped: DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY not configured. "
            "Points without coordinates in CSV will be imported without lat/lng."
        )

    try:
        from django_regional.models import Country as _Country

        _country_model = _Country
    except ImportError:
        _country_model = None

    for row in rows:
        code = row["delivery-point-code"]
        row_warnings: list[str] = []

        # Resolve coordinates
        lat = None
        lng = None
        geocoded = False

        if has_coords:
            raw_x = row.get("delivery-point-x", "").strip()
            raw_y = row.get("delivery-point-y", "").strip()
            if raw_x and raw_y:
                lng = float(raw_x)
                lat = float(raw_y)
                if lat == 0.0 and lng == 0.0:
                    lat = lng = None  # Treat 0,0 as placeholder — trigger geocode

        if lat is None or lng is None:
            lat, lng, geocoded = _try_geocode(row)
            if geocoded:
                result.geocoded += 1
            elif geocoding_service.is_available():
                result.geocode_failed += 1

        # Validate coordinate ranges
        if lat is not None and not (-90 <= lat <= 90):
            row_warnings.append(f"Latitude {lat} out of range [-90, 90], cleared")
            logger.warning("Row %s: latitude %s out of range, cleared", code, lat)
            lat = None
        if lng is not None and not (-180 <= lng <= 180):
            row_warnings.append(f"Longitude {lng} out of range [-180, 180], cleared")
            logger.warning("Row %s: longitude %s out of range, cleared", code, lng)
            lng = None

        # Validate and resolve country
        country_raw = row.get("delivery-point-country", "").strip()
        country = ""
        if country_raw:
            country_upper = country_raw.upper()
            if _country_model is not None:
                if _country_model.objects.filter(iso2=country_upper).exists():
                    country = country_upper
                else:
                    row_warnings.append(f"Invalid country code: {country_raw}")
                    logger.warning("Row %s: invalid country code %r", code, country_raw)
            else:
                row_warnings.append(f"Could not validate country: {country_raw}")
                logger.warning("Row %s: django_regional not available, skipping country", code)

        defaults = {
            "name": row["delivery-point-name"],
            "street": row.get("delivery-point-address", ""),
            "city": row.get("delivery-point-city", ""),
            "post_code": row.get("delivery-point-postcode", ""),
            "hint": row.get("delivery-point-hint", ""),
            "phone": row.get("delivery-point-phone", ""),
            "website": row.get("delivery-point-website", ""),
            "email": row.get("delivery-point-email", ""),
            "country": country,
            "is_active": True,
        }
        if lat is not None:
            defaults["latitude"] = lat
        if lng is not None:
            defaults["longitude"] = lng

        existing = DeliveryPoint.objects.filter(type=dp_type, code=code).first()
        changed_fields = _detect_changes(existing, defaults) if existing else []

        point, created = DeliveryPoint.objects.update_or_create(type=dp_type, code=code, defaults=defaults)
        if channel is not None:
            point.channels.add(channel)

        if created:
            result.created += 1
            entry = {"code": code, "name": defaults["name"], "action": "created"}
            if geocoded:
                entry["geocoded"] = True
            if row_warnings:
                entry["warnings"] = row_warnings
                result.warnings += 1
            entries.append(entry)
        else:
            result.updated += 1
            entry = {"code": code, "name": defaults["name"], "action": "updated"}
            if changed_fields:
                entry["changed_fields"] = changed_fields
            if geocoded:
                entry["geocoded"] = True
            if row_warnings:
                entry["warnings"] = row_warnings
                result.warnings += 1
            entries.append(entry)
        imported_codes.add(code)

    if mode == "full":
        qs = DeliveryPoint.objects.filter(type=dp_type, is_active=True)
        if channel is not None:
            qs = qs.filter(channels=channel)
        else:
            qs = qs.filter(channels=None)
        to_disable = qs.exclude(code__in=imported_codes)
        for point in to_disable:
            entries.append({"code": point.code, "name": point.name, "action": "disabled"})
        disabled_count = to_disable.update(is_active=False)
        result.disabled = disabled_count

    ImportLog.objects.create(
        type=dp_type,
        mode=mode,
        channel=channel,
        created_count=result.created,
        updated_count=result.updated,
        disabled_count=result.disabled,
        entries=entries,
        source=source,
    )

    return result
