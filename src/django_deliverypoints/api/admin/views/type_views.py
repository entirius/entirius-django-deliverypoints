# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for delivery point types."""

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django_utils.api.v2_errors import raise_pydantic_as_drf
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_deliverypoints.api.admin.pagination import AdminPageNumberPagination
from django_deliverypoints.api.admin.permissions import IsAdminUser
from django_deliverypoints.schemas.requests.type_request import (
    DeliveryPointTypeCreateRequest,
    DeliveryPointTypeUpdateRequest,
)
from django_deliverypoints.schemas.responses.type_response import (
    DeliveryPointTypeListResponse,
    DeliveryPointTypeResponse,
)
from django_deliverypoints.services import type_service

_ERROR_RESPONSES = {
    400: {"description": "Validation error"},
    401: {"description": "Authentication required"},
    403: {"description": "Permission denied"},
    404: {"description": "Not found"},
}


@extend_schema_view(
    list=extend_schema(tags=["Delivery Point Types"]),
    create=extend_schema(tags=["Delivery Point Types"]),
    retrieve=extend_schema(tags=["Delivery Point Types"]),
    partial_update=extend_schema(tags=["Delivery Point Types"]),
    destroy=extend_schema(tags=["Delivery Point Types"]),
)
class TypeViewSet(viewsets.ViewSet):
    """Admin CRUD for delivery point types."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List delivery point types",
        description="Returns a paginated list of all delivery point types, including inactive ones.",
        parameters=[
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
            OpenApiParameter(
                name="page_size", location=OpenApiParameter.QUERY, type=int, description="Items per page (max 100)"
            ),
        ],
        responses={200: DeliveryPointTypeListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        qs = type_service.list_types(include_inactive=True)
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [DeliveryPointTypeResponse.model_validate(t) for t in page]
        response = DeliveryPointTypeListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Create delivery point type",
        description="Creates a new delivery point type with the provided data.",
        responses={201: DeliveryPointTypeResponse, **_ERROR_RESPONSES},
    )
    def create(self, request: Request, **kwargs) -> Response:
        try:
            data = DeliveryPointTypeCreateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        try:
            dp_type = type_service.create_type(
                code=data.code,
                name=data.name,
                is_carrier=data.is_carrier,
                is_active=data.is_active,
                sort_order=data.sort_order,
            )
        except IntegrityError:
            return Response(
                {"detail": f"Type with code '{data.code}' already exists."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(DeliveryPointTypeResponse.model_validate(dp_type).model_dump(), status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Retrieve delivery point type",
        description="Returns a single delivery point type by its primary key.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Type primary key")
        ],
        responses={200: DeliveryPointTypeResponse, **_ERROR_RESPONSES},
    )
    def retrieve(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            dp_type = type_service.get_type_by_pk(pk=int(pk))
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DeliveryPointTypeResponse.model_validate(dp_type).model_dump())

    @extend_schema(
        summary="Update delivery point type",
        description="Partially updates a delivery point type. Only provided fields are changed.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Type primary key")
        ],
        responses={200: DeliveryPointTypeResponse, **_ERROR_RESPONSES},
    )
    def partial_update(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            data = DeliveryPointTypeUpdateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        updates = data.model_dump(exclude_none=True)
        try:
            dp_type = type_service.update_type(pk=int(pk), **updates)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(DeliveryPointTypeResponse.model_validate(dp_type).model_dump())

    @extend_schema(
        summary="Delete delivery point type",
        description="Deletes a delivery point type. Raises 409 if points of this type exist.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Type primary key")
        ],
        responses={204: None, **_ERROR_RESPONSES, 409: {"description": "Cannot delete: points exist"}},
    )
    def destroy(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            type_service.delete_type(pk=int(pk))
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
