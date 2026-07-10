# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.urls import path

from django_deliverypoints.api.public.views.point_views import PublicPointViewSet
from django_deliverypoints.api.public.views.type_views import PublicTypeViewSet

urlpatterns = [
    path("<str:channel_idx>/points/", PublicPointViewSet.as_view({"get": "list"}), name="public-point-list"),
    path("<str:channel_idx>/points/nearby/", PublicPointViewSet.as_view({"get": "nearby"}), name="public-point-nearby"),
    path(
        "<str:channel_idx>/points/<int:pk>/",
        PublicPointViewSet.as_view({"get": "retrieve"}),
        name="public-point-detail",
    ),
    path("<str:channel_idx>/types/", PublicTypeViewSet.as_view({"get": "list"}), name="public-type-list"),
]
