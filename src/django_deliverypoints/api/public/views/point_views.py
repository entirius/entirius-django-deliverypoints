# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public delivery point read-only API views."""

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from django_deliverypoints.api.admin.pagination import AdminPageNumberPagination
from django_deliverypoints.models import DeliveryPoint, DeliveryPointChannel
from django_deliverypoints.schemas.responses.point import PublicPointListResponse, PublicPointResponse
from django_deliverypoints.services import channel_service, point_service

_CHANNEL_IDX_PARAM = OpenApiParameter(
    name="channel_idx", location=OpenApiParameter.PATH, description="Channel identifier", required=True, type=str
)

_SEARCH_PARAM = OpenApiParameter(
    name="search",
    location=OpenApiParameter.QUERY,
    description="Search by name, code, city, post code, or street",
    required=False,
    type=str,
)

_TYPE_PARAM = OpenApiParameter(
    name="type",
    location=OpenApiParameter.QUERY,
    description="Filter by delivery point type code (e.g. inpost, dpd)",
    required=False,
    type=str,
)

_ORDERING_PARAM = OpenApiParameter(
    name="ordering",
    location=OpenApiParameter.QUERY,
    description="Sort field: name, city (prefix with - for descending)",
    required=False,
    type=str,
)

_LANGUAGE_PARAM = OpenApiParameter(
    name="language",
    location=OpenApiParameter.QUERY,
    description="Language ISO2 code for translated fields (e.g. de, pl)",
    required=False,
    type=str,
)


def _build_public_point_response(
    point: DeliveryPoint,
    channel: DeliveryPointChannel | None = None,
    language: str | None = None,
    distance: float | None = None,
) -> PublicPointResponse:
    """Map a DeliveryPoint ORM instance to PublicPointResponse with T9N fallback."""
    translated = point_service.resolve_translation(point, channel, language)
    return PublicPointResponse(
        id=point.pk,
        type_code=point.type.code,
        type_name=point.type.name,
        is_carrier=point.type.is_carrier,
        code=point.code,
        name=translated["name"],
        latitude=point.latitude,
        longitude=point.longitude,
        street=point.street,
        city=point.city,
        state=point.state,
        post_code=point.post_code,
        country=point.country,
        phone=point.phone,
        email=point.email,
        website=point.website,
        opening_hours=translated["opening_hours"],
        hint=translated["hint"],
        distance=getattr(point, "distance", distance),
    )


@extend_schema_view(
    list=extend_schema(
        summary="List delivery points",
        description=(
            "Returns paginated active delivery points for the given channel. "
            "Includes both global carrier points (channel=null) and channel-specific points. "
            "Use ?language= to get translated name, hint, and opening_hours fields."
        ),
        tags=["Public Delivery Points"],
        parameters=[_CHANNEL_IDX_PARAM, _SEARCH_PARAM, _TYPE_PARAM, _ORDERING_PARAM, _LANGUAGE_PARAM],
        responses={200: PublicPointListResponse, 400: {"description": "Invalid request"}},
    ),
    retrieve=extend_schema(
        summary="Retrieve delivery point",
        description="Returns a single active delivery point by ID, scoped to the given channel.",
        tags=["Public Delivery Points"],
        parameters=[_CHANNEL_IDX_PARAM, _LANGUAGE_PARAM],
        responses={200: PublicPointResponse, 404: {"description": "Point not found or not accessible in this channel"}},
    ),
)
class PublicPointViewSet(viewsets.ViewSet):
    """Public delivery point read-only API."""

    authentication_classes = []
    permission_classes = [AllowAny]
    pagination_class = AdminPageNumberPagination

    def list(self, request: Request, channel_idx: str = "", **kwargs) -> Response:
        search = request.query_params.get("search")
        type_code = request.query_params.get("type")
        ordering = request.query_params.get("ordering")
        language = request.query_params.get("language")

        channel = channel_service.get_channel_or_none(channel_idx)
        qs = point_service.public_list_points(
            channel_idx=channel_idx, search=search, type_code=type_code, ordering=ordering
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        results = [_build_public_point_response(point, channel, language) for point in page]
        response_data = PublicPointListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response_data.model_dump())

    def retrieve(self, request: Request, channel_idx: str = "", pk: int = 0, **kwargs) -> Response:
        language = request.query_params.get("language")
        channel = channel_service.get_channel_or_none(channel_idx)

        try:
            point = point_service.public_get_point(channel_idx=channel_idx, pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(_build_public_point_response(point, channel, language).model_dump())

    @extend_schema(
        summary="List nearby delivery points",
        description=(
            "Returns active delivery points within the given radius using Haversine geo search. "
            "Results are ordered by distance ascending. "
            "Requires lat and lng query parameters."
        ),
        tags=["Public Delivery Points"],
        parameters=[
            _CHANNEL_IDX_PARAM,
            OpenApiParameter(
                name="lat",
                location=OpenApiParameter.QUERY,
                description="WGS84 latitude of search origin",
                required=True,
                type=float,
            ),
            OpenApiParameter(
                name="lng",
                location=OpenApiParameter.QUERY,
                description="WGS84 longitude of search origin",
                required=True,
                type=float,
            ),
            OpenApiParameter(
                name="radius_km",
                location=OpenApiParameter.QUERY,
                description="Search radius in kilometres (default from settings)",
                required=False,
                type=float,
            ),
            _TYPE_PARAM,
            _LANGUAGE_PARAM,
        ],
        responses={200: PublicPointListResponse, 400: {"description": "Missing or invalid lat/lng parameters"}},
    )
    @action(detail=False, methods=["get"], url_path="nearby")
    def nearby(self, request: Request, channel_idx: str = "", **kwargs) -> Response:
        lat_raw = request.query_params.get("lat")
        lng_raw = request.query_params.get("lng")

        if lat_raw is None or lng_raw is None:
            return Response(
                {"detail": "lat and lng query parameters are required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lat = float(lat_raw)
            lng = float(lng_raw)
        except ValueError:
            return Response({"detail": "lat and lng must be valid numbers."}, status=status.HTTP_400_BAD_REQUEST)

        radius_km: float | None = None
        radius_raw = request.query_params.get("radius_km")
        if radius_raw is not None:
            try:
                radius_km = float(radius_raw)
            except ValueError:
                return Response({"detail": "radius_km must be a valid number."}, status=status.HTTP_400_BAD_REQUEST)

        type_code = request.query_params.get("type")
        language = request.query_params.get("language")
        channel = channel_service.get_channel_or_none(channel_idx)

        qs = point_service.public_nearby_points(
            channel_idx=channel_idx, lat=lat, lng=lng, radius_km=radius_km, type_code=type_code
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        results = [_build_public_point_response(point, channel, language) for point in page]
        response_data = PublicPointListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response_data.model_dump())
