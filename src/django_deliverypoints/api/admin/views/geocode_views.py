# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin geocode search endpoint."""

from django_utils.api.v2_errors import raise_pydantic_as_drf
from drf_spectacular.utils import extend_schema, inline_serializer
from pydantic import ValidationError
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_deliverypoints.api.admin.permissions import IsAdminUser
from django_deliverypoints.schemas.requests.geocode import GeocodeSearchRequest, GeocodeSearchResult
from django_deliverypoints.services import geocoding_service


class GeocodeSearchView(APIView):
    """Search addresses via Google Maps Geocoding API."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "deliverypoints.points"
    access_levels = {"POST": "read"}

    @extend_schema(
        tags=["Delivery Points"],
        summary="Search addresses for geocoding",
        description=(
            "Search for addresses using Google Maps Geocoding API. "
            "Returns structured address data with coordinates. "
            "When API key is not configured, returns availability status."
        ),
        request=GeocodeSearchRequest,
        responses={
            200: inline_serializer(
                name="GeocodeSearchResultList",
                fields={
                    "formatted_address": serializers.CharField(),
                    "latitude": serializers.DecimalField(max_digits=10, decimal_places=7),
                    "longitude": serializers.DecimalField(max_digits=10, decimal_places=7),
                    "street": serializers.CharField(),
                    "city": serializers.CharField(),
                    "state": serializers.CharField(),
                    "post_code": serializers.CharField(),
                    "country": serializers.CharField(),
                },
                many=True,
            )
        },
    )
    def post(self, request: Request) -> Response:
        if not geocoding_service.is_available():
            return Response(
                {
                    "available": False,
                    "message": (
                        "Google Maps API key not configured. "
                        "Set DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY in Django settings."
                    ),
                }
            )

        try:
            data = GeocodeSearchRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        results = geocoding_service.search_addresses(query=data.query, country_bias=data.country_bias, limit=data.limit)

        return Response(
            [
                GeocodeSearchResult(
                    formatted_address=r.formatted_address,
                    latitude=r.latitude,
                    longitude=r.longitude,
                    street=r.street,
                    city=r.city,
                    state=r.state,
                    post_code=r.post_code,
                    country=r.country,
                ).model_dump()
                for r in results
            ]
        )
