# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for delivery point CSV imports."""

import codecs

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_deliverypoints.api.admin.permissions import IsAdminUser
from django_deliverypoints.schemas.responses.import_result import ImportResultResponse
from django_deliverypoints.services import channel_service, import_service


class ImportView(APIView):
    """CSV import endpoint for delivery points."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["Delivery Point Import"],
        summary="Import delivery points from CSV",
        description=(
            "Uploads a CSV file and imports delivery points for the given type. "
            "Mode 'incremental' upserts rows without touching missing points. "
            "Mode 'full' upserts rows and sets is_active=False on missing points of that type."
        ),
        responses={
            200: ImportResultResponse,
            400: {"description": "Validation error or empty CSV"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
            404: {"description": "Type or channel not found"},
        },
    )
    def post(self, request: Request, **kwargs) -> Response:
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Field 'file' is required."}, status=status.HTTP_400_BAD_REQUEST)

        type_code = request.data.get("type_code", "").strip()
        if not type_code:
            return Response({"detail": "Field 'type_code' is required."}, status=status.HTTP_400_BAD_REQUEST)

        mode = request.data.get("mode", "incremental").strip()
        if mode not in ("incremental", "full"):
            return Response(
                {"detail": "Field 'mode' must be 'incremental' or 'full'."}, status=status.HTTP_400_BAD_REQUEST
            )

        channel_idx = request.data.get("channel_idx", "").strip() or None
        channel = None
        if channel_idx is not None:
            try:
                channel = channel_service.get_channel(channel_idx)
            except ObjectDoesNotExist:
                return Response({"detail": f"Channel '{channel_idx}' not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            text_file = codecs.getreader("utf-8")(file)
            result = import_service.import_csv(
                file=text_file, type_code=type_code, mode=mode, channel=channel, source="api"
            )
        except ObjectDoesNotExist:
            return Response({"detail": f"DeliveryPointType '{type_code}' not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response = ImportResultResponse(created=result.created, updated=result.updated, disabled=result.disabled)
        return Response(response.model_dump())
