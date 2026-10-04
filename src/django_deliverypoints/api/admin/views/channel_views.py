# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for delivery point channels."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_deliverypoints.api.admin.pagination import AdminPageNumberPagination
from django_deliverypoints.api.admin.permissions import IsAdminUser
from django_deliverypoints.schemas.responses.channel import DPChannelListResponse, DPChannelResponse
from django_deliverypoints.services import channel_service


def _build_channel_response(ch) -> dict:
    """Build DPChannelResponse dict from ORM instance."""
    return DPChannelResponse(
        id=ch.pk,
        idx=ch.idx,
        name=ch.name,
        default_language_iso2=(ch.default_language.iso2 if ch.default_language else None),
        language_codes=list(ch.languages.values_list("iso2", flat=True)),
    ).model_dump()


@extend_schema_view(list=extend_schema(tags=["Delivery Point Channels"]))
class ChannelViewSet(viewsets.ViewSet):
    """Admin read-only access to delivery point channels with sync action."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "deliverypoints.points"

    @extend_schema(
        summary="List delivery point channels",
        description="Returns all delivery point channels.",
        responses={
            200: DPChannelListResponse,
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
        },
    )
    def list(self, request: Request, **kwargs) -> Response:
        qs = channel_service.list_channels()
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [_build_channel_response(ch) for ch in page]
        response = DPChannelListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Sync channels from PIM",
        description="Syncs delivery point channels from PIM Channel model.",
        tags=["Delivery Point Channels"],
        responses={
            200: {"description": "Sync result"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
        },
    )
    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request: Request, **kwargs) -> Response:
        count = channel_service.sync_channels_from_pim()
        return Response({"synced": count}, status=status.HTTP_200_OK)
