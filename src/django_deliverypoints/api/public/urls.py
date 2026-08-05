# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.urls import path
from django.views.decorators.cache import cache_page

from django_deliverypoints.api.public.views.point_views import PublicPointViewSet
from django_deliverypoints.api.public.views.type_views import PublicTypeViewSet
from django_deliverypoints.settings import CACHE_TTL, USE_CACHED_VIEWS


def _apply_cache(view):
    """View cache, same switches as django-matrix (USE_CACHED_VIEWS + CACHE_TTL).

    cache_page stores the response server-side (Django cache framework) and
    sets the Cache-Control: max-age header for browser/CDN caching.
    """
    if USE_CACHED_VIEWS and isinstance(CACHE_TTL, int):
        return cache_page(CACHE_TTL)(view)
    return view


urlpatterns = [
    path(
        "<str:channel_idx>/points/",
        _apply_cache(PublicPointViewSet.as_view({"get": "list"})),
        name="public-point-list",
    ),
    # nearby is NOT cached: lat/lng query params are unique per user position,
    # so cache entries would never be reused
    path("<str:channel_idx>/points/nearby/", PublicPointViewSet.as_view({"get": "nearby"}), name="public-point-nearby"),
    path(
        "<str:channel_idx>/points/<int:pk>/",
        _apply_cache(PublicPointViewSet.as_view({"get": "retrieve"})),
        name="public-point-detail",
    ),
    path(
        "<str:channel_idx>/types/",
        _apply_cache(PublicTypeViewSet.as_view({"get": "list"})),
        name="public-type-list",
    ),
]
