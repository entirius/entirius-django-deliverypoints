# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Point management service."""

import re
from unicodedata import normalize

from django.db.models import Q, QuerySet

from django_deliverypoints.models import DeliveryPoint, DeliveryPointChannel, DeliveryPointT9N
from django_deliverypoints.services import channel_service, geo_service


def list_points(
    *,
    include_inactive: bool = False,
    all_channels: bool = False,
    channel_idx: str | None = None,
    type_code: str | None = None,
    city: str | None = None,
    country: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    ordering: str | None = None,
) -> QuerySet[DeliveryPoint]:
    """List points with optional filters.

    Args:
        all_channels: When True, no channel filter is applied (admin global view).
        channel_idx: When provided, filters to points for that channel.
                     When None and all_channels=False, returns only global points.
    """
    qs = DeliveryPoint.objects.select_related("type").all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if type_code is not None:
        if type_code == "carrier":
            qs = qs.filter(type__is_carrier=True)
        elif type_code == "custom":
            qs = qs.filter(type__is_carrier=False)
        else:
            qs = qs.filter(type__code=type_code)
    if not all_channels:
        if channel_idx is not None:
            dp_channel = channel_service.get_channel(channel_idx)
            qs = qs.filter(channels=dp_channel)
        else:
            qs = qs.filter(channels=None)
    if city is not None:
        qs = qs.filter(city__icontains=city)
    if country is not None:
        qs = qs.filter(country__iexact=country)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search is not None:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(city__icontains=search)
            | Q(post_code__icontains=search)
            | Q(street__icontains=search)
        )
    if ordering is not None:
        qs = qs.order_by(ordering)
    return qs.distinct()


def get_point(*, pk: int) -> DeliveryPoint:
    """Get point by PK. Raises ObjectDoesNotExist."""
    return DeliveryPoint.objects.select_related("type").get(pk=pk)


def _generate_code(name: str, dp_type) -> str:
    """Generate a unique code from name, slugified. Appends -2, -3 etc. on collision."""
    # Normalize unicode, strip accents, lowercase, replace non-alphanum with hyphens
    slug = normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", slug).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    slug = slug[:100]
    if not slug:
        slug = "point"

    candidate = slug
    counter = 2
    while DeliveryPoint.objects.filter(type=dp_type, code=candidate).exists():
        suffix = f"-{counter}"
        candidate = slug[: 100 - len(suffix)] + suffix
        counter += 1
    return candidate


def create_point(
    *, type, code: str | None = None, name: str, channel_ids: list[int] | None = None, **kwargs
) -> DeliveryPoint:
    """Create a new point. Returns instance with type pre-fetched."""
    if not code:
        code = _generate_code(name, type)
    point = DeliveryPoint.objects.create(type=type, code=code, name=name, **kwargs)
    if channel_ids:
        channels = channel_service.get_channels_by_pks(channel_ids)
        point.channels.set(channels)
    return DeliveryPoint.objects.select_related("type").prefetch_related("channels").get(pk=point.pk)


_CARRIER_EDITABLE_FIELDS = frozenset({"is_active"})


def update_point(*, pk: int, channel_ids: list[int] | None = None, type=None, **kwargs) -> DeliveryPoint:
    """Update point fields. Returns updated instance with type pre-fetched.

    Carrier points are managed by the import system: only is_active can change.
    Type can only be changed to another custom (non-carrier) type.
    """
    point = DeliveryPoint.objects.select_related("type").get(pk=pk)
    if point.type.is_carrier:
        blocked = set(kwargs) - _CARRIER_EDITABLE_FIELDS
        if blocked or type is not None or channel_ids is not None:
            raise ValueError("Carrier points are managed by the import system; only is_active can be changed.")
    if type is not None:
        if type.is_carrier:
            raise ValueError("Cannot change point type to a carrier type.")
        point.type = type
    for field, value in kwargs.items():
        setattr(point, field, value)
    point.save()
    if channel_ids is not None:
        channels = channel_service.get_channels_by_pks(channel_ids)
        point.channels.set(channels)
    return DeliveryPoint.objects.select_related("type").prefetch_related("channels").get(pk=point.pk)


def delete_point(*, pk: int) -> None:
    """Delete point from DB."""
    DeliveryPoint.objects.get(pk=pk).delete()


def resolve_translation(
    point: DeliveryPoint, channel: DeliveryPointChannel | None = None, language_iso2: str | None = None
) -> dict:
    """Resolve translated fields for a point using fallback chain.

    Fallback: requested language → channel.default_language → base fields.
    Returns dict with keys: name, hint, opening_hours.
    """
    base = {"name": point.name, "hint": point.hint, "opening_hours": point.opening_hours}
    if not language_iso2:
        return base

    # Try requested language
    t9n = DeliveryPointT9N.objects.filter(point=point, language__iso2__iexact=language_iso2).first()
    if t9n:
        return _t9n_to_dict(t9n, base)

    # Try channel default language
    if channel and channel.default_language:
        t9n = DeliveryPointT9N.objects.filter(point=point, language=channel.default_language).first()
        if t9n:
            return _t9n_to_dict(t9n, base)

    return base


_VALID_PUBLIC_ORDERINGS = {"name", "-name", "city", "-city"}


def public_list_points(
    *, channel_idx: str, search: str | None = None, type_code: str | None = None, ordering: str | None = None
) -> QuerySet[DeliveryPoint]:
    """List active points scoped to channel (global + channel-specific)."""
    qs = (
        DeliveryPoint.objects.filter(Q(channels=None) | Q(channels__idx=channel_idx), is_active=True)
        .select_related("type")
        .distinct()
    )
    if type_code is not None:
        qs = qs.filter(type__code=type_code)
    if search is not None:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(city__icontains=search)
            | Q(post_code__icontains=search)
            | Q(street__icontains=search)
        )
    if ordering is not None and ordering in _VALID_PUBLIC_ORDERINGS:
        qs = qs.order_by(ordering)
    return qs


def public_get_point(*, channel_idx: str, pk: int) -> DeliveryPoint:
    """Get single active point scoped to channel. Raises ObjectDoesNotExist."""
    return DeliveryPoint.objects.select_related("type").get(
        Q(channels=None) | Q(channels__idx=channel_idx), pk=pk, is_active=True
    )


def public_nearby_points(
    *, channel_idx: str, lat: float, lng: float, radius_km: float | None = None, type_code: str | None = None
) -> QuerySet[DeliveryPoint]:
    """Find nearby active points scoped to channel."""
    qs = geo_service.find_nearby(lat=lat, lng=lng, radius_km=radius_km, type_code=type_code)
    return qs.filter(Q(channels=None) | Q(channels__idx=channel_idx)).select_related("type").distinct()


def _t9n_to_dict(t9n: DeliveryPointT9N, base: dict) -> dict:
    """Build translation dict, falling back to base fields for empty values."""
    return {
        "name": t9n.name or base["name"],
        "hint": t9n.hint or base["hint"],
        "opening_hours": t9n.opening_hours or base["opening_hours"],
    }
