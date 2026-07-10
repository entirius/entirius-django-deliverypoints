# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.urls import path

from django_deliverypoints.api.admin.views.channel_views import ChannelViewSet
from django_deliverypoints.api.admin.views.country_views import CountryListView
from django_deliverypoints.api.admin.views.geocode_views import GeocodeSearchView
from django_deliverypoints.api.admin.views.import_views import ImportView
from django_deliverypoints.api.admin.views.point_views import PointViewSet
from django_deliverypoints.api.admin.views.t9n_views import PointT9NViewSet
from django_deliverypoints.api.admin.views.type_views import TypeViewSet

urlpatterns = [
    # Types (global)
    path("types/", TypeViewSet.as_view({"get": "list", "post": "create"}), name="admin-type-list"),
    path(
        "types/<int:pk>/",
        TypeViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="admin-type-detail",
    ),
    # Channels
    path("channels/", ChannelViewSet.as_view({"get": "list"}), name="admin-channel-list"),
    path("channels/sync/", ChannelViewSet.as_view({"post": "sync"}), name="admin-channel-sync"),
    # Countries
    path("countries/", CountryListView.as_view(), name="admin-country-list"),
    # Points (global — all points)
    path("points/", PointViewSet.as_view({"get": "list", "post": "create"}), name="admin-point-list"),
    path(
        "points/<int:pk>/",
        PointViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="admin-point-detail",
    ),
    # Point translations
    path(
        "points/<int:point_pk>/translations/",
        PointT9NViewSet.as_view({"get": "list", "post": "create"}),
        name="admin-point-t9n-list",
    ),
    path(
        "points/<int:point_pk>/translations/<str:language>/",
        PointT9NViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="admin-point-t9n-detail",
    ),
    # Points (channel-scoped view)
    path("<str:channel_idx>/points/", PointViewSet.as_view({"get": "list"}), name="admin-point-list-channel"),
    # Geocode search
    path("geocode/search/", GeocodeSearchView.as_view(), name="admin-geocode-search"),
    # Import (global)
    path("import/", ImportView.as_view(), name="admin-import"),
]
