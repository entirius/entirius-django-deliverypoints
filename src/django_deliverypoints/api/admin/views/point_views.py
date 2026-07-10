# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for delivery points."""

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django_utils.api.v2_errors import raise_pydantic_as_drf
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_deliverypoints.api.admin.pagination import AdminPageNumberPagination
from django_deliverypoints.api.admin.permissions import IsAdminUser
from django_deliverypoints.schemas.requests.point import DeliveryPointCreateRequest, DeliveryPointUpdateRequest
from django_deliverypoints.schemas.responses.point import DeliveryPointListResponse, DeliveryPointResponse
from django_deliverypoints.services import point_service, type_service

_ERROR_RESPONSES = {
    400: {"description": "Validation error"},
    401: {"description": "Authentication required"},
    403: {"description": "Permission denied"},
    404: {"description": "Not found"},
}

_VALID_ORDERINGS = {
    "name",
    "-name",
    "city",
    "-city",
    "type",
    "-type",
    "is_active",
    "-is_active",
    "created_at",
    "-created_at",
}


def _parse_bool_param(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() in ("true", "1", "yes")


def _build_response(point) -> dict:
    """Build DeliveryPointResponse dict from ORM instance with M2M channels and translations."""
    from django_deliverypoints.models import DeliveryPointT9N
    from django_deliverypoints.schemas.responses.t9n import PointT9NResponse

    channel_ids = list(point.channels.values_list("pk", flat=True))
    t9ns = DeliveryPointT9N.objects.filter(point=point).select_related("language")
    translations = [
        PointT9NResponse(language=t.language.iso2, name=t.name, hint=t.hint, opening_hours=t.opening_hours).model_dump()
        for t in t9ns
    ]
    response = DeliveryPointResponse(
        id=point.pk,
        type=point.type,
        channel_ids=channel_ids,
        translations=translations,
        code=point.code,
        name=point.name,
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
        opening_hours=point.opening_hours,
        hint=point.hint,
        is_active=point.is_active,
        created_at=point.created_at,
        modified_at=point.modified_at,
    )
    return response.model_dump()


@extend_schema_view(
    list=extend_schema(tags=["Delivery Points"]),
    create=extend_schema(tags=["Delivery Points"]),
    retrieve=extend_schema(tags=["Delivery Points"]),
    partial_update=extend_schema(tags=["Delivery Points"]),
    destroy=extend_schema(tags=["Delivery Points"]),
)
class PointViewSet(viewsets.ViewSet):
    """Admin CRUD for delivery points. Serves both global and channel-scoped list paths."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List delivery points",
        description=(
            "Returns a paginated list of delivery points. "
            "When called via the channel-scoped URL, filters to points for that channel. "
            "When called via the global URL, returns all points across all channels."
        ),
        parameters=[
            OpenApiParameter(
                name="channel_idx",
                location=OpenApiParameter.PATH,
                type=str,
                required=False,
                description="Channel identifier (channel-scoped path only)",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Search by name, code, city, post_code, or street",
            ),
            OpenApiParameter(
                name="type", location=OpenApiParameter.QUERY, type=str, description="Filter by delivery point type code"
            ),
            OpenApiParameter(
                name="city", location=OpenApiParameter.QUERY, type=str, description="Filter by city (case-insensitive)"
            ),
            OpenApiParameter(
                name="country",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter by country code (ISO 3166-1 alpha-2)",
            ),
            OpenApiParameter(
                name="is_active", location=OpenApiParameter.QUERY, type=bool, description="Filter by active status"
            ),
            OpenApiParameter(
                name="ordering",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Order by field: name, city, type, is_active, created_at (prefix with - for descending)",
            ),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
            OpenApiParameter(
                name="page_size", location=OpenApiParameter.QUERY, type=int, description="Items per page (max 100)"
            ),
        ],
        responses={200: DeliveryPointListResponse, **_ERROR_RESPONSES},
        examples=[
            OpenApiExample(
                name="Delivery point list",
                summary="Paginated delivery point list",
                description="Delivery points for a channel with InPost locker and showroom.",
                value={
                    "count": 2,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "type": "inpost",
                            "channel_ids": [],
                            "translations": [],
                            "code": "WAW042",
                            "name": "InPost Locker WAW042",
                            "latitude": "52.2297700",
                            "longitude": "21.0117800",
                            "street": "ul. Marszałkowska 1",
                            "city": "Warszawa",
                            "state": "mazowieckie",
                            "post_code": "00-001",
                            "country": "PL",
                            "phone": None,
                            "email": None,
                            "website": None,
                            "opening_hours": {"mon-fri": "06:00-22:00", "sat-sun": "08:00-20:00"},
                            "hint": "Next to the main entrance",
                            "is_active": True,
                            "created_at": "2025-01-15T10:30:00Z",
                            "modified_at": "2025-01-15T10:30:00Z",
                        }
                    ],
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def list(self, request: Request, **kwargs) -> Response:
        channel_idx = kwargs.get("channel_idx")
        ordering = request.query_params.get("ordering")
        if ordering and ordering not in _VALID_ORDERINGS:
            return Response({"detail": f"Invalid ordering: {ordering}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            qs = point_service.list_points(
                include_inactive=True,
                all_channels=channel_idx is None,
                channel_idx=channel_idx,
                type_code=request.query_params.get("type") or None,
                city=request.query_params.get("city") or None,
                country=request.query_params.get("country") or None,
                is_active=_parse_bool_param(request.query_params.get("is_active")),
                search=request.query_params.get("search") or None,
                ordering=ordering,
            )
        except ObjectDoesNotExist:
            return Response({"detail": f"Channel '{channel_idx}' not found."}, status=status.HTTP_404_NOT_FOUND)

        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [_build_response(p) for p in page]
        response = DeliveryPointListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Create delivery point",
        description="Creates a new delivery point. Supply type_id (DeliveryPointType PK) and required fields.",
        responses={201: DeliveryPointResponse, **_ERROR_RESPONSES},
    )
    def create(self, request: Request, **kwargs) -> Response:
        try:
            data = DeliveryPointCreateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        try:
            dp_type = type_service.get_type_by_pk(pk=data.type_id)
        except ObjectDoesNotExist:
            return Response(
                {"detail": f"DeliveryPointType {data.type_id} not found."}, status=status.HTTP_400_BAD_REQUEST
            )

        if dp_type.is_carrier:
            return Response(
                {"detail": "Cannot create points with carrier types. Carrier points are managed by the import system."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_kwargs = data.model_dump(exclude={"type_id", "channel_ids"})
        try:
            point = point_service.create_point(type=dp_type, channel_ids=data.channel_ids, **create_kwargs)
        except IntegrityError:
            return Response(
                {"detail": f"Point with code '{data.code}' already exists for this type."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_build_response(point), status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Retrieve delivery point",
        description="Returns a single delivery point by its primary key.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Point primary key")
        ],
        responses={200: DeliveryPointResponse, **_ERROR_RESPONSES},
    )
    def retrieve(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            point = point_service.get_point(pk=int(pk))
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_build_response(point))

    @extend_schema(
        summary="Update delivery point",
        description="Partially updates a delivery point. Only provided fields are changed.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Point primary key")
        ],
        responses={200: DeliveryPointResponse, **_ERROR_RESPONSES},
    )
    def partial_update(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            data = DeliveryPointUpdateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        channel_ids = data.channel_ids
        updates = data.model_dump(exclude={"channel_ids"}, exclude_none=True)
        try:
            point = point_service.update_point(pk=int(pk), channel_ids=channel_ids, **updates)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_build_response(point))

    @extend_schema(
        summary="Delete delivery point",
        description="Permanently deletes a delivery point by its primary key.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Point primary key")
        ],
        responses={204: None, **_ERROR_RESPONSES},
    )
    def destroy(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            point_service.delete_point(pk=int(pk))
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
