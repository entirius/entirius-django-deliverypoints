# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Geo search service (Haversine-based nearby lookup)."""

from django.db.models import FloatField, QuerySet
from django.db.models.expressions import RawSQL

from django_deliverypoints import settings
from django_deliverypoints.models import DeliveryPoint

_HAVERSINE_SQL = """
    6371 * acos(
        LEAST(1.0, GREATEST(-1.0,
            cos(radians(%s)) * cos(radians(latitude)) *
            cos(radians(longitude) - radians(%s)) +
            sin(radians(%s)) * sin(radians(latitude))
        ))
    )
"""


def find_nearby(
    *, lat: float, lng: float, radius_km: float | None = None, type_code: str | None = None
) -> QuerySet[DeliveryPoint]:
    """Find active points within radius using Haversine formula."""
    if radius_km is None:
        radius_km = settings.DEFAULT_SEARCH_RADIUS_KM

    qs = DeliveryPoint.objects.filter(is_active=True, latitude__isnull=False, longitude__isnull=False)
    if type_code is not None:
        qs = qs.filter(type__code=type_code)

    qs = qs.annotate(distance=RawSQL(_HAVERSINE_SQL, (lat, lng, lat), output_field=FloatField()))
    return qs.filter(distance__lte=radius_km).order_by("distance")
