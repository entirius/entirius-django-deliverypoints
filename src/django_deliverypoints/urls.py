# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.urls import include, path

app_name = "django_deliverypoints"

urlpatterns = [
    path("api/deliverypoints/v2/admin/", include("django_deliverypoints.api.admin.urls")),
    path("api/deliverypoints/v2/", include("django_deliverypoints.api.public.urls")),
]
