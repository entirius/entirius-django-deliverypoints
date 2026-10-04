# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API view for listing available countries."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_deliverypoints.api.admin.permissions import IsAdminUser


class CountryListView(APIView):
    """Returns list of all available countries from django_regional."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "deliverypoints.points"

    @extend_schema(
        summary="List countries",
        description="Returns all available countries with ISO 3166-1 alpha-2 codes.",
        tags=["Delivery Point Countries"],
        responses={
            200: {"description": "List of countries"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
        },
    )
    def get(self, request: Request) -> Response:
        from django_regional.models import Country

        countries = Country.objects.all().order_by("name_en")
        results = [{"iso2": c.iso2, "name": c.name_en} for c in countries]
        return Response(results, status=status.HTTP_200_OK)
