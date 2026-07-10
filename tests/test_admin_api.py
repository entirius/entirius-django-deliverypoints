# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Integration tests for the django-deliverypoints admin API (v2).

Covers all endpoints under /api/deliverypoints/v2/admin/ including:
- Authentication: 401 / 403 / 200 for every guarded route
- Types: list, create, retrieve, update, delete (including 409 PROTECT)
- Points: list, create, retrieve, update, delete (with filters and ordering)
- Channel-scoped point list
- CSV import: incremental, full, error cases
- Geocode search endpoint
- Auto-generated point codes
"""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django_deliverypoints.models import DeliveryPoint, DeliveryPointChannel, DeliveryPointT9N, DeliveryPointType

from .factories import DeliveryPointChannelFactory, DeliveryPointFactory, DeliveryPointTypeFactory

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

TYPES_LIST_URL = "/api/deliverypoints/v2/admin/types/"
IMPORT_URL = "/api/deliverypoints/v2/admin/import/"
POINTS_LIST_URL = "/api/deliverypoints/v2/admin/points/"
CHANNELS_LIST_URL = "/api/deliverypoints/v2/admin/channels/"
CHANNELS_SYNC_URL = "/api/deliverypoints/v2/admin/channels/sync/"
GEOCODE_SEARCH_URL = "/api/deliverypoints/v2/admin/geocode/search/"
COUNTRIES_LIST_URL = "/api/deliverypoints/v2/admin/countries/"


def type_detail_url(pk: int) -> str:
    return f"/api/deliverypoints/v2/admin/types/{pk}/"


def point_detail_url(pk: int) -> str:
    return f"/api/deliverypoints/v2/admin/points/{pk}/"


def channel_points_url(channel_idx: str) -> str:
    return f"/api/deliverypoints/v2/admin/{channel_idx}/points/"


def point_t9n_list_url(point_pk: int) -> str:
    return f"/api/deliverypoints/v2/admin/points/{point_pk}/translations/"


def point_t9n_detail_url(point_pk: int, language: str) -> str:
    return f"/api/deliverypoints/v2/admin/points/{point_pk}/translations/{language}/"


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

CSV_HEADER = (
    "delivery-point-x,delivery-point-y,delivery-point-name,"
    "delivery-point-code,delivery-point-type,delivery-point-address,"
    "delivery-point-city,delivery-point-postcode,delivery-point-hint"
)


def _csv_row(
    x: float,
    y: float,
    name: str,
    code: str,
    type_code: str,
    address: str = "ul. Testowa 1",
    city: str = "Warszawa",
    postcode: str = "00-001",
    hint: str = "",
) -> str:
    return f"{x},{y},{name},{code},{type_code},{address},{city},{postcode},{hint}"


def _make_csv_upload(*rows: str, filename: str = "points.csv") -> SimpleUploadedFile:
    content = "\n".join([CSV_HEADER, *rows])
    return SimpleUploadedFile(filename, content.encode("utf-8"), content_type="text/csv")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin", email="admin@test.com", password="adminpass123", is_staff=True, is_superuser=False
    )


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username="regular", email="regular@test.com", password="regularpass123", is_staff=False, is_superuser=False
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_user(
        username="super", email="super@test.com", password="superpass123", is_staff=False, is_superuser=True
    )


@pytest.fixture
def admin_token(admin_user):
    return str(RefreshToken.for_user(admin_user).access_token)


@pytest.fixture
def regular_token(regular_user):
    return str(RefreshToken.for_user(regular_user).access_token)


@pytest.fixture
def superuser_token(superuser):
    return str(RefreshToken.for_user(superuser).access_token)


@pytest.fixture
def authenticated_client(api_client, admin_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
    return api_client


def _make_channel(idx: str = "test-channel"):
    """Create a DeliveryPointChannel instance."""
    channel, _ = DeliveryPointChannel.objects.get_or_create(idx=idx, defaults={"name": f"Channel {idx}"})
    return channel


# ---------------------------------------------------------------------------
# 1. TestAuthentication
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuthentication:
    def test_unauthenticated_request_returns_401(self, api_client):
        # Act
        response = api_client.get(TYPES_LIST_URL)

        # Assert
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, api_client):
        # Arrange
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")

        # Act
        response = api_client.get(TYPES_LIST_URL)

        # Assert
        assert response.status_code == 401

    def test_regular_user_returns_403(self, api_client, regular_token):
        # Arrange
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {regular_token}")

        # Act
        response = api_client.get(TYPES_LIST_URL)

        # Assert
        assert response.status_code == 403

    def test_admin_user_returns_200(self, api_client, admin_token):
        # Arrange
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")

        # Act
        response = api_client.get(TYPES_LIST_URL)

        # Assert
        assert response.status_code == 200

    def test_superuser_returns_200(self, api_client, superuser_token):
        # Arrange
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {superuser_token}")

        # Act
        response = api_client.get(TYPES_LIST_URL)

        # Assert
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 2. TestTypeList
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTypeList:
    def test_list_types_returns_paginated(self, authenticated_client):
        # Arrange
        DeliveryPointTypeFactory.create_batch(3)

        # Act
        response = authenticated_client.get(TYPES_LIST_URL)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "results" in data
        assert "next" in data
        assert "previous" in data
        assert data["count"] >= 3
        assert len(data["results"]) >= 3

    def test_list_types_includes_inactive(self, authenticated_client):
        # Arrange
        active = DeliveryPointTypeFactory(is_active=True)
        inactive = DeliveryPointTypeFactory(is_active=False)

        # Act
        response = authenticated_client.get(TYPES_LIST_URL)

        # Assert
        assert response.status_code == 200
        result_ids = [t["id"] for t in response.json()["results"]]
        assert active.pk in result_ids
        assert inactive.pk in result_ids


# ---------------------------------------------------------------------------
# 3. TestTypeCreate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTypeCreate:
    def test_create_type(self, authenticated_client):
        # Arrange
        payload = {"code": "orlen", "name": "Orlen Paczka", "is_carrier": True}

        # Act
        response = authenticated_client.post(TYPES_LIST_URL, payload, format="json")

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "orlen"
        assert data["name"] == "Orlen Paczka"
        assert data["is_carrier"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_type_duplicate_code_returns_400(self, authenticated_client):
        # Arrange
        DeliveryPointTypeFactory(code="inpost")

        # Act
        response = authenticated_client.post(TYPES_LIST_URL, {"code": "inpost", "name": "Duplicate"}, format="json")

        # Assert
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 4. TestTypeRetrieve
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTypeRetrieve:
    def test_retrieve_type(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="dpd", name="DPD")

        # Act
        response = authenticated_client.get(type_detail_url(dp_type.pk))

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dp_type.pk
        assert data["code"] == "dpd"
        assert data["name"] == "DPD"

    def test_retrieve_type_not_found(self, authenticated_client):
        # Act
        response = authenticated_client.get(type_detail_url(999999))

        # Assert
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 5. TestTypeUpdate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTypeUpdate:
    def test_update_type(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory(name="Old Name")

        # Act
        response = authenticated_client.patch(type_detail_url(dp_type.pk), {"name": "New Name"}, format="json")

        # Assert
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"
        dp_type.refresh_from_db()
        assert dp_type.name == "New Name"

    def test_update_type_not_found(self, authenticated_client):
        # Act
        response = authenticated_client.patch(type_detail_url(999999), {"name": "Ghost"}, format="json")

        # Assert
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 6. TestTypeDelete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTypeDelete:
    def test_delete_type(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        pk = dp_type.pk

        # Act
        response = authenticated_client.delete(type_detail_url(pk))

        # Assert
        assert response.status_code == 204
        assert not DeliveryPointType.objects.filter(pk=pk).exists()

    def test_delete_type_not_found(self, authenticated_client):
        # Act
        response = authenticated_client.delete(type_detail_url(999999))

        # Assert
        assert response.status_code == 404

    def test_delete_type_with_points_returns_409(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type)

        # Act
        response = authenticated_client.delete(type_detail_url(dp_type.pk))

        # Assert — PROTECT raises ProtectedError, view maps to 409
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# 6b. TestCarrierTypeAPI
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCarrierTypeAPI:
    def test_update_carrier_returns_403(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory(is_carrier=True, code="carrier-test")

        # Act
        response = authenticated_client.patch(type_detail_url(dp_type.pk), {"name": "Changed"}, format="json")

        # Assert
        assert response.status_code == 403

    def test_delete_carrier_returns_403(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory(is_carrier=True, code="carrier-del")

        # Act
        response = authenticated_client.delete(type_detail_url(dp_type.pk))

        # Assert
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# 7. TestPointList
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointList:
    def test_list_points_returns_paginated(self, authenticated_client):
        # Arrange
        DeliveryPointFactory.create_batch(3)

        # Act
        response = authenticated_client.get(POINTS_LIST_URL)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 3

    def test_list_points_search(self, authenticated_client):
        # Arrange
        match = DeliveryPointFactory(code="WAW-CENTRAL-01", name="Warsaw Central")
        DeliveryPointFactory(code="KRK-001", name="Krakow Point")

        # Act
        response = authenticated_client.get(POINTS_LIST_URL, {"search": "WAW"})

        # Assert
        assert response.status_code == 200
        result_ids = [p["id"] for p in response.json()["results"]]
        assert match.pk in result_ids

    def test_list_points_filter_by_type(self, authenticated_client):
        # Arrange
        inpost_type = DeliveryPointTypeFactory(code="inpost")
        dpd_type = DeliveryPointTypeFactory(code="dpd")
        inpost_point = DeliveryPointFactory(type=inpost_type)
        DeliveryPointFactory(type=dpd_type)

        # Act
        response = authenticated_client.get(POINTS_LIST_URL, {"type": "inpost"})

        # Assert
        assert response.status_code == 200
        results = response.json()["results"]
        result_ids = [p["id"] for p in results]
        assert inpost_point.pk in result_ids
        assert all(p["type"]["code"] == "inpost" for p in results)

    def test_list_points_filter_by_city(self, authenticated_client):
        # Arrange
        warsaw_point = DeliveryPointFactory(city="Warsaw")
        DeliveryPointFactory(city="Krakow")

        # Act
        response = authenticated_client.get(POINTS_LIST_URL, {"city": "Warsaw"})

        # Assert
        assert response.status_code == 200
        result_ids = [p["id"] for p in response.json()["results"]]
        assert warsaw_point.pk in result_ids

    def test_list_points_filter_by_is_active(self, authenticated_client):
        # Arrange
        active = DeliveryPointFactory(is_active=True)
        DeliveryPointFactory(is_active=False)

        # Act
        response = authenticated_client.get(POINTS_LIST_URL, {"is_active": "true"})

        # Assert
        assert response.status_code == 200
        results = response.json()["results"]
        result_ids = [p["id"] for p in results]
        assert active.pk in result_ids
        assert all(p["is_active"] is True for p in results)

    def test_list_points_ordering(self, authenticated_client):
        # Arrange
        DeliveryPointFactory(city="Zielona Gora")
        DeliveryPointFactory(city="Bialystok")
        DeliveryPointFactory(city="Lodz")

        # Act
        response = authenticated_client.get(POINTS_LIST_URL, {"ordering": "city"})

        # Assert
        assert response.status_code == 200
        cities = [p["city"] for p in response.json()["results"]]
        assert cities == sorted(cities)

    def test_list_points_invalid_ordering_returns_400(self, authenticated_client):
        # Act
        response = authenticated_client.get(POINTS_LIST_URL, {"ordering": "invalid_field"})

        # Assert
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 8. TestPointCreate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointCreate:
    def test_create_point(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        payload = {
            "type_id": dp_type.pk,
            "code": "POP-WAW-001",
            "name": "Warsaw Central Locker",
            "city": "Warsaw",
            "country": "PL",
        }

        # Act
        response = authenticated_client.post(POINTS_LIST_URL, payload, format="json")

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "POP-WAW-001"
        assert data["name"] == "Warsaw Central Locker"
        assert data["type"]["id"] == dp_type.pk
        assert "id" in data

    def test_create_point_invalid_type_returns_400(self, authenticated_client):
        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": 999999, "code": "GHOST-001", "name": "Ghost Point"}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_create_carrier_point_returns_400(self, authenticated_client):
        # Arrange — carrier types cannot be used for manual point creation
        carrier_type = DeliveryPointTypeFactory(is_carrier=True, code="carrier-blk")

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": carrier_type.pk, "code": "C-001", "name": "Carrier Point"}, format="json"
        )

        # Assert
        assert response.status_code == 400
        assert "carrier" in response.json()["detail"].lower()

    def test_create_point_with_channel_ids(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        channel = _make_channel("ch-create")

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL,
            {"type_id": dp_type.pk, "code": "CH-001", "name": "Channel Point", "channel_ids": [channel.pk]},
            format="json",
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert channel.pk in data["channel_ids"]

    def test_create_point_without_channels_is_global(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "code": "GLOBAL-001", "name": "Global Point"}, format="json"
        )

        # Assert
        assert response.status_code == 201
        assert response.json()["channel_ids"] == []

    def test_create_point_with_multiple_channels(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        ch1 = _make_channel("ch-multi-1")
        ch2 = _make_channel("ch-multi-2")

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL,
            {
                "type_id": dp_type.pk,
                "code": "MULTI-001",
                "name": "Multi Channel Point",
                "channel_ids": [ch1.pk, ch2.pk],
            },
            format="json",
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert set(data["channel_ids"]) == {ch1.pk, ch2.pk}


# ---------------------------------------------------------------------------
# 9. TestPointRetrieve
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointRetrieve:
    def test_retrieve_point(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory(name="Test Point", code="TP-001")

        # Act
        response = authenticated_client.get(point_detail_url(point.pk))

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == point.pk
        assert data["code"] == "TP-001"
        assert data["name"] == "Test Point"
        assert "type" in data

    def test_retrieve_point_not_found(self, authenticated_client):
        # Act
        response = authenticated_client.get(point_detail_url(999999))

        # Assert
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 10. TestPointUpdate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointUpdate:
    def test_update_point(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory(name="Old Name")

        # Act
        response = authenticated_client.patch(point_detail_url(point.pk), {"name": "Updated Name"}, format="json")

        # Assert
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        point.refresh_from_db()
        assert point.name == "Updated Name"

    def test_update_point_not_found(self, authenticated_client):
        # Act
        response = authenticated_client.patch(point_detail_url(999999), {"name": "Ghost"}, format="json")

        # Assert
        assert response.status_code == 404

    def test_update_point_channel_ids(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        ch = _make_channel("ch-upd")

        # Act — assign channels
        response = authenticated_client.patch(point_detail_url(point.pk), {"channel_ids": [ch.pk]}, format="json")

        # Assert
        assert response.status_code == 200
        assert ch.pk in response.json()["channel_ids"]

    def test_update_point_clear_channels_makes_global(self, authenticated_client):
        # Arrange
        ch = _make_channel("ch-clear")
        point = DeliveryPointFactory(channels=[ch])

        # Act — empty list = global
        response = authenticated_client.patch(point_detail_url(point.pk), {"channel_ids": []}, format="json")

        # Assert
        assert response.status_code == 200
        assert response.json()["channel_ids"] == []

    def test_update_point_null_channels_leaves_unchanged(self, authenticated_client):
        # Arrange
        ch = _make_channel("ch-null")
        point = DeliveryPointFactory(channels=[ch])

        # Act — null = don't change
        response = authenticated_client.patch(point_detail_url(point.pk), {"name": "New Name"}, format="json")

        # Assert
        assert response.status_code == 200
        assert ch.pk in response.json()["channel_ids"]


# ---------------------------------------------------------------------------
# 11. TestPointDelete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointDelete:
    def test_delete_point(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        pk = point.pk

        # Act
        response = authenticated_client.delete(point_detail_url(pk))

        # Assert
        assert response.status_code == 204
        assert not DeliveryPoint.objects.filter(pk=pk).exists()

    def test_delete_point_not_found(self, authenticated_client):
        # Act
        response = authenticated_client.delete(point_detail_url(999999))

        # Assert
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 12. TestPointListChannelScoped
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointListChannelScoped:
    def test_list_points_by_channel(self, authenticated_client):
        # Arrange
        channel = _make_channel("shop-01")
        channel_point = DeliveryPointFactory(channels=[channel])
        DeliveryPointFactory()  # global point (no channels) — must not appear

        # Act
        response = authenticated_client.get(channel_points_url("shop-01"))

        # Assert
        assert response.status_code == 200
        result_ids = [p["id"] for p in response.json()["results"]]
        assert channel_point.pk in result_ids

    def test_list_points_channel_not_found_returns_404(self, authenticated_client):
        # Act
        response = authenticated_client.get(channel_points_url("nonexistent-channel-xyz"))

        # Assert
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 13. TestImport
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestImport:
    def test_import_csv_incremental(self, authenticated_client):
        # Arrange
        DeliveryPointTypeFactory(code="inpost")
        csv_file = _make_csv_upload(
            _csv_row(21.0200, 52.2350, "Point A", "IMP-001", "inpost"),
            _csv_row(21.0400, 52.2500, "Point B", "IMP-002", "inpost"),
        )

        # Act
        response = authenticated_client.post(
            IMPORT_URL, {"file": csv_file, "type_code": "inpost", "mode": "incremental"}, format="multipart"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 2
        assert data["updated"] == 0
        assert data["disabled"] == 0

    def test_import_csv_full_disables_missing(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        existing = DeliveryPointFactory(type=dp_type, code="OLD-001", is_active=True)
        csv_file = _make_csv_upload(_csv_row(21.0200, 52.2350, "New Point", "NEW-001", "inpost"))

        # Act
        response = authenticated_client.post(
            IMPORT_URL, {"file": csv_file, "type_code": "inpost", "mode": "full"}, format="multipart"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 1
        assert data["disabled"] >= 1
        existing.refresh_from_db()
        assert existing.is_active is False

    def test_import_missing_file_returns_400(self, authenticated_client):
        # Act
        response = authenticated_client.post(
            IMPORT_URL, {"type_code": "inpost", "mode": "incremental"}, format="multipart"
        )

        # Assert
        assert response.status_code == 400

    def test_import_missing_type_code_returns_400(self, authenticated_client):
        # Arrange
        csv_file = _make_csv_upload(_csv_row(21.0200, 52.2350, "Point A", "IMP-001", "inpost"))

        # Act
        response = authenticated_client.post(IMPORT_URL, {"file": csv_file, "mode": "incremental"}, format="multipart")

        # Assert
        assert response.status_code == 400

    def test_import_invalid_mode_returns_400(self, authenticated_client):
        # Arrange
        csv_file = _make_csv_upload(_csv_row(21.0200, 52.2350, "Point A", "IMP-001", "inpost"))

        # Act
        response = authenticated_client.post(
            IMPORT_URL, {"file": csv_file, "type_code": "inpost", "mode": "batch"}, format="multipart"
        )

        # Assert
        assert response.status_code == 400

    def test_import_unknown_type_returns_404(self, authenticated_client):
        # Arrange
        csv_file = _make_csv_upload(_csv_row(21.0200, 52.2350, "Point A", "IMP-001", "nonexistent"))

        # Act
        response = authenticated_client.post(
            IMPORT_URL, {"file": csv_file, "type_code": "nonexistent", "mode": "incremental"}, format="multipart"
        )

        # Assert
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 14. TestChannelList
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestChannelList:
    def test_list_channels(self, authenticated_client):
        # Arrange
        DeliveryPointChannelFactory.create_batch(3)

        # Act
        response = authenticated_client.get(CHANNELS_LIST_URL)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 3

    def test_list_channels_response_structure(self, authenticated_client):
        # Arrange
        _make_channel("struct-ch")

        # Act
        response = authenticated_client.get(CHANNELS_LIST_URL)

        # Assert
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert "id" in result
        assert "idx" in result
        assert "name" in result
        assert "default_language_iso2" in result
        assert "language_codes" in result

    def test_list_channels_unauthenticated_returns_401(self, api_client):
        # Act
        response = api_client.get(CHANNELS_LIST_URL)

        # Assert
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# 15. TestChannelSync
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestChannelSync:
    def test_sync_channels(self, authenticated_client):
        # Act
        response = authenticated_client.post(CHANNELS_SYNC_URL)

        # Assert
        assert response.status_code == 200
        assert "synced" in response.json()


# ---------------------------------------------------------------------------
# 16. TestPointT9N
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointT9N:
    def _create_language(self, iso2: str):
        from django_regional.models import Language

        lang, _ = Language.objects.get_or_create(
            iso2=iso2, defaults={"iso3": iso2 + "u", "name_en": iso2.upper(), "name_pl": iso2.upper()}
        )
        return lang

    def test_list_translations_empty(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()

        # Act
        response = authenticated_client.get(point_t9n_list_url(point.pk))

        # Assert
        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_create_translation(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        self._create_language("de")

        # Act
        response = authenticated_client.post(
            point_t9n_list_url(point.pk), {"language": "de", "name": "German Name", "hint": "Hinweis"}, format="json"
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["language"] == "de"
        assert data["name"] == "German Name"
        assert data["hint"] == "Hinweis"

    def test_create_translation_duplicate_returns_400(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        lang = self._create_language("de")
        DeliveryPointT9N.objects.create(point=point, language=lang, name="Exists")

        # Act
        response = authenticated_client.post(
            point_t9n_list_url(point.pk), {"language": "de", "name": "Duplicate"}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_create_translation_unknown_language_returns_400(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()

        # Act
        response = authenticated_client.post(
            point_t9n_list_url(point.pk), {"language": "zz", "name": "Unknown"}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_update_translation(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        lang = self._create_language("de")
        DeliveryPointT9N.objects.create(point=point, language=lang, name="Old")

        # Act
        response = authenticated_client.patch(point_t9n_detail_url(point.pk, "de"), {"name": "Updated"}, format="json")

        # Assert
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    def test_delete_translation(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        lang = self._create_language("de")
        DeliveryPointT9N.objects.create(point=point, language=lang, name="Delete Me")

        # Act
        response = authenticated_client.delete(point_t9n_detail_url(point.pk, "de"))

        # Assert
        assert response.status_code == 204
        assert not DeliveryPointT9N.objects.filter(point=point, language=lang).exists()

    def test_delete_translation_not_found_returns_404(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()

        # Act
        response = authenticated_client.delete(point_t9n_detail_url(point.pk, "zz"))

        # Assert
        assert response.status_code == 404

    def test_list_translations_returns_all(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        de = self._create_language("de")
        pl = self._create_language("pl")
        DeliveryPointT9N.objects.create(point=point, language=de, name="German")
        DeliveryPointT9N.objects.create(point=point, language=pl, name="Polish")

        # Act
        response = authenticated_client.get(point_t9n_list_url(point.pk))

        # Assert
        assert response.status_code == 200
        data = response.json()["results"]
        assert len(data) == 2
        languages = {t["language"] for t in data}
        assert languages == {"de", "pl"}

    def test_point_response_includes_translations(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()
        lang = self._create_language("de")
        DeliveryPointT9N.objects.create(point=point, language=lang, name="German Name")

        # Act
        response = authenticated_client.get(point_detail_url(point.pk))

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "translations" in data
        assert len(data["translations"]) == 1
        assert data["translations"][0]["language"] == "de"


# ---------------------------------------------------------------------------
# 17. TestGeocodeSearch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGeocodeSearch:
    def test_geocode_search_unauthenticated_returns_401(self, api_client):
        # Act
        response = api_client.post(GEOCODE_SEARCH_URL, {"query": "Marszalkowska 1, Warszawa"}, format="json")

        # Assert
        assert response.status_code == 401

    def test_geocode_search_regular_user_returns_403(self, api_client, regular_token):
        # Arrange
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {regular_token}")

        # Act
        response = api_client.post(GEOCODE_SEARCH_URL, {"query": "Marszalkowska 1, Warszawa"}, format="json")

        # Assert
        assert response.status_code == 403

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="")
    def test_geocode_search_no_api_key_returns_unavailable(self, _mock_key, authenticated_client):
        # Act
        response = authenticated_client.post(GEOCODE_SEARCH_URL, {"query": "Marszalkowska 1, Warszawa"}, format="json")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert "message" in data

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="test-key")
    @patch("django_deliverypoints.services.geocoding_service.requests.get")
    def test_geocode_search_returns_results(self, mock_get, _mock_key, authenticated_client):
        # Arrange
        mock_get.return_value.json.return_value = {
            "results": [
                {
                    "formatted_address": "Marszalkowska 1, 00-624 Warszawa, Poland",
                    "geometry": {"location": {"lat": 52.2296756, "lng": 21.0122287}},
                    "address_components": [
                        {"long_name": "1", "short_name": "1", "types": ["street_number"]},
                        {"long_name": "Marszalkowska", "short_name": "Marszalkowska", "types": ["route"]},
                        {"long_name": "Warszawa", "short_name": "Warszawa", "types": ["locality"]},
                        {"long_name": "PL", "short_name": "PL", "types": ["country"]},
                    ],
                }
            ],
            "status": "OK",
        }
        mock_get.return_value.raise_for_status = lambda: None

        # Act
        response = authenticated_client.post(GEOCODE_SEARCH_URL, {"query": "Marszalkowska 1, Warszawa"}, format="json")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["city"] == "Warszawa"
        assert str(data[0]["latitude"]) == "52.2296756"

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="test-key")
    def test_geocode_search_short_query_returns_400(self, _mock_key, authenticated_client):
        # Act
        response = authenticated_client.post(GEOCODE_SEARCH_URL, {"query": "ab"}, format="json")

        # Assert
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 18. TestPointCreateAutoCode
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPointCreateAutoCode:
    def test_create_point_without_code_auto_generates(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL,
            {"type_id": dp_type.pk, "name": "Warsaw Showroom", "city": "Warsaw", "country": "PL"},
            format="json",
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "warsaw-showroom"
        assert data["name"] == "Warsaw Showroom"

    def test_create_point_with_code_uses_provided(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL,
            {"type_id": dp_type.pk, "code": "CUSTOM-CODE-01", "name": "Custom Code Point"},
            format="json",
        )

        # Assert
        assert response.status_code == 201
        assert response.json()["code"] == "CUSTOM-CODE-01"

    def test_create_point_auto_code_dedup(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, code="test-point")

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "Test Point"}, format="json"
        )

        # Assert
        assert response.status_code == 201
        assert response.json()["code"] == "test-point-2"


# ---------------------------------------------------------------------------
# 19. TestImportWithoutCoords
# ---------------------------------------------------------------------------

CSV_HEADER_NO_COORDS = (
    "delivery-point-name,delivery-point-code,delivery-point-type,"
    "delivery-point-address,delivery-point-city,delivery-point-postcode,delivery-point-hint"
)


def _make_csv_upload_no_coords(*rows: str, filename: str = "points.csv") -> SimpleUploadedFile:
    content = "\n".join([CSV_HEADER_NO_COORDS, *rows])
    return SimpleUploadedFile(filename, content.encode("utf-8"), content_type="text/csv")


@pytest.mark.django_db
class TestImportWithoutCoords:
    @patch("django_deliverypoints.services.import_service.geocoding_service.is_available", return_value=False)
    def test_import_no_coords_no_geocoding_creates_points(self, _mock_avail, authenticated_client):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        csv_file = _make_csv_upload_no_coords("My Showroom,SHW-001,showroom,Main St 1,Warsaw,00-001,Near park")

        # Act
        response = authenticated_client.post(
            IMPORT_URL, {"file": csv_file, "type_code": "showroom", "mode": "incremental"}, format="multipart"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 1
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="SHW-001")
        assert point.latitude is None
        assert point.longitude is None
        assert point.city == "Warsaw"


# ---------------------------------------------------------------------------
# 20. TestFieldValidation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFieldValidation:
    def _create_country(self, iso2: str, name_en: str = ""):
        from django_regional.models import Country

        if not Country.objects.filter(iso2=iso2).exists():
            Country.objects.bulk_create(
                [
                    Country(
                        iso2=iso2, iso3=iso2.lower() + "x", name_en=name_en or iso2, name_pl=name_en or iso2, prefix=""
                    )
                ]
            )

    def test_create_point_invalid_country_returns_400(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "Test Point", "country": "XX"}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_create_point_valid_country_lowercase_uppercased(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        self._create_country("PL", "Poland")

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "Test Point", "country": "pl"}, format="json"
        )

        # Assert
        assert response.status_code == 201
        assert response.json()["country"] == "PL"

    def test_create_point_latitude_over_90_returns_400(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "Bad Lat", "latitude": 91.0}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_create_point_latitude_under_minus90_returns_400(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "Bad Lat", "latitude": -91.0}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_create_point_longitude_over_180_returns_400(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "Bad Lon", "longitude": 181.0}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_create_point_longitude_under_minus180_returns_400(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "Bad Lon", "longitude": -181.0}, format="json"
        )

        # Assert
        assert response.status_code == 400

    def test_update_point_invalid_country_returns_400(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()

        # Act
        response = authenticated_client.patch(point_detail_url(point.pk), {"country": "ZZ"}, format="json")

        # Assert
        assert response.status_code == 400

    def test_update_point_latitude_over_90_returns_400(self, authenticated_client):
        # Arrange
        point = DeliveryPointFactory()

        # Act
        response = authenticated_client.patch(point_detail_url(point.pk), {"latitude": 95.0}, format="json")

        # Assert
        assert response.status_code == 400

    def test_create_point_valid_coords_succeeds(self, authenticated_client):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL,
            {"type_id": dp_type.pk, "name": "Valid Coords", "latitude": 52.2297, "longitude": 21.0122},
            format="json",
        )

        # Assert
        assert response.status_code == 201

    def test_create_point_empty_country_succeeds(self, authenticated_client):
        # Arrange — empty string country should pass (not validated)
        dp_type = DeliveryPointTypeFactory()

        # Act
        response = authenticated_client.post(
            POINTS_LIST_URL, {"type_id": dp_type.pk, "name": "No Country", "country": ""}, format="json"
        )

        # Assert
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# 21. TestCountriesList
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountriesList:
    def _create_country(self, iso2: str, name_en: str):
        from django_regional.models import Country

        if not Country.objects.filter(iso2=iso2).exists():
            Country.objects.bulk_create(
                [Country(iso2=iso2, iso3=iso2.lower() + "x", name_en=name_en, name_pl=name_en, prefix="")]
            )

    def test_list_countries_returns_200(self, authenticated_client):
        # Arrange
        self._create_country("PL", "Poland")
        self._create_country("DE", "Germany")

        # Act
        response = authenticated_client.get(COUNTRIES_LIST_URL)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_countries_response_structure(self, authenticated_client):
        # Arrange
        self._create_country("PL", "Poland")

        # Act
        response = authenticated_client.get(COUNTRIES_LIST_URL)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        country = data[0]
        assert "iso2" in country
        assert "name" in country

    def test_list_countries_unauthenticated_returns_401(self, api_client):
        # Act
        response = api_client.get(COUNTRIES_LIST_URL)

        # Assert
        assert response.status_code == 401

    def test_list_countries_regular_user_returns_403(self, api_client, regular_token):
        # Arrange
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {regular_token}")

        # Act
        response = api_client.get(COUNTRIES_LIST_URL)

        # Assert
        assert response.status_code == 403
