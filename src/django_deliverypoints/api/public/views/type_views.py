# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public delivery point type read-only API views."""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from django_deliverypoints.api.admin.pagination import AdminPageNumberPagination
from django_deliverypoints.schemas.responses.type_response import PublicTypeListResponse, PublicTypeResponse
from django_deliverypoints.services import type_service

_CHANNEL_IDX_PARAM = OpenApiParameter(
    name="channel_idx", location=OpenApiParameter.PATH, description="Channel identifier", required=True, type=str
)


@extend_schema_view(
    list=extend_schema(
        summary="List delivery point types",
        description=(
            "Returns all active delivery point types. "
            "Types are global (not channel-scoped). "
            "Use is_carrier to distinguish carrier lockers from custom location types."
        ),
        tags=["Public Delivery Point Types"],
        parameters=[_CHANNEL_IDX_PARAM],
        responses={200: PublicTypeListResponse},
    )
)
class PublicTypeViewSet(viewsets.ViewSet):
    """Public delivery point type read-only API."""

    authentication_classes = []
    permission_classes = [AllowAny]
    pagination_class = AdminPageNumberPagination

    def list(self, request: Request, channel_idx: str = "", **kwargs) -> Response:
        qs = type_service.list_types()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        results = [PublicTypeResponse.model_validate(t) for t in page]
        response_data = PublicTypeListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response_data.model_dump())
