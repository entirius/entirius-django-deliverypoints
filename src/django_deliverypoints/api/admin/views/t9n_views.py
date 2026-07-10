# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for delivery point translations."""

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django_utils.api.v2_errors import raise_pydantic_as_drf
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_deliverypoints.api.admin.permissions import IsAdminUser
from django_deliverypoints.models import DeliveryPoint, DeliveryPointT9N
from django_deliverypoints.schemas.requests.t9n import PointT9NCreateRequest, PointT9NUpdateRequest
from django_deliverypoints.schemas.responses.t9n import PointT9NListResponse, PointT9NResponse

_PK_PARAM = OpenApiParameter(
    name="point_pk", location=OpenApiParameter.PATH, type=int, description="Delivery point primary key"
)

_LANG_PARAM = OpenApiParameter(
    name="language", location=OpenApiParameter.PATH, type=str, description="Language ISO2 code"
)


def _build_t9n_response(t9n: DeliveryPointT9N) -> dict:
    return PointT9NResponse(
        language=t9n.language.iso2, name=t9n.name, hint=t9n.hint, opening_hours=t9n.opening_hours
    ).model_dump()


@extend_schema_view(
    list=extend_schema(tags=["Delivery Point Translations"]),
    create=extend_schema(tags=["Delivery Point Translations"]),
    partial_update=extend_schema(tags=["Delivery Point Translations"]),
    destroy=extend_schema(tags=["Delivery Point Translations"]),
)
class PointT9NViewSet(viewsets.ViewSet):
    """Admin CRUD for delivery point translations."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List translations for a point",
        description="Returns all translations for the given delivery point.",
        parameters=[_PK_PARAM],
        responses={
            200: PointT9NListResponse,
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
            404: {"description": "Point not found"},
        },
    )
    def list(self, request: Request, point_pk: int, **kwargs) -> Response:
        try:
            DeliveryPoint.objects.get(pk=point_pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Point not found."}, status=status.HTTP_404_NOT_FOUND)

        t9ns = DeliveryPointT9N.objects.filter(point_id=point_pk).select_related("language")
        response = PointT9NListResponse(results=[_build_t9n_response(t) for t in t9ns])
        return Response(response.model_dump())

    @extend_schema(
        summary="Create translation for a point",
        description="Creates a new translation for the given delivery point and language.",
        parameters=[_PK_PARAM],
        responses={
            201: PointT9NResponse,
            400: {"description": "Validation error"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
            404: {"description": "Point not found"},
        },
    )
    def create(self, request: Request, point_pk: int, **kwargs) -> Response:
        try:
            data = PointT9NCreateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        try:
            point = DeliveryPoint.objects.get(pk=point_pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Point not found."}, status=status.HTTP_404_NOT_FOUND)

        from django_regional.models import Language

        lang = Language.objects.filter(iso2__iexact=data.language).first()
        if not lang:
            return Response({"detail": f"Language '{data.language}' not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            t9n = DeliveryPointT9N.objects.create(
                point=point, language=lang, name=data.name, hint=data.hint, opening_hours=data.opening_hours
            )
        except IntegrityError:
            return Response(
                {"detail": f"Translation for language '{data.language}' already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        t9n = DeliveryPointT9N.objects.select_related("language").get(pk=t9n.pk)
        return Response(_build_t9n_response(t9n), status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Update translation for a point",
        description="Updates the translation for the given point and language.",
        parameters=[_PK_PARAM, _LANG_PARAM],
        responses={
            200: PointT9NResponse,
            400: {"description": "Validation error"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
            404: {"description": "Translation not found"},
        },
    )
    def partial_update(self, request: Request, point_pk: int, language: str, **kwargs) -> Response:
        try:
            data = PointT9NUpdateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        try:
            t9n = DeliveryPointT9N.objects.select_related("language").get(
                point_id=point_pk, language__iso2__iexact=language
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Translation not found."}, status=status.HTTP_404_NOT_FOUND)

        updates = data.model_dump(exclude_none=True)
        for field, value in updates.items():
            setattr(t9n, field, value)
        t9n.save()

        return Response(_build_t9n_response(t9n))

    @extend_schema(
        summary="Delete translation for a point",
        description="Deletes the translation for the given point and language.",
        parameters=[_PK_PARAM, _LANG_PARAM],
        responses={
            204: None,
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
            404: {"description": "Translation not found"},
        },
    )
    def destroy(self, request: Request, point_pk: int, language: str, **kwargs) -> Response:
        try:
            t9n = DeliveryPointT9N.objects.get(point_id=point_pk, language__iso2__iexact=language)
        except ObjectDoesNotExist:
            return Response({"detail": "Translation not found."}, status=status.HTTP_404_NOT_FOUND)

        t9n.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
