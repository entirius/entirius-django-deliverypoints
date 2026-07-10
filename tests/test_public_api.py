# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Integration tests for the public delivery points API (AllowAny, channel-scoped)."""

from decimal import Decimal

import pytest
from django_regional.models import Language
from rest_framework.test import APIClient

from django_deliverypoints.models import DeliveryPointChannel, DeliveryPointT9N

from .factories import DeliveryPointFactory, DeliveryPointTypeFactory

# ---------------------------------------------------------------------------
# Reference coordinates (WGS84)
# ---------------------------------------------------------------------------

WARSAW_CENTER = (52.2297, 21.0122)
POINT_1_KM = (52.2350, 21.0200)
POINT_3_KM = (52.2500, 21.0400)
POINT_50_KM = (52.7000, 21.5000)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def channel(db):
    lang, _ = Language.objects.get_or_create(
        iso2="pl", defaults={"iso3": "pol", "name_en": "Polish", "name_pl": "Polski"}
    )
    ch = DeliveryPointChannel.objects.create(idx="test-channel", name="Test Channel", default_language=lang)
    ch.languages.add(lang)
    return ch


@pytest.fixture
def other_channel(db):
    lang, _ = Language.objects.get_or_create(
        iso2="en", defaults={"iso3": "eng", "name_en": "English", "name_pl": "Angielski"}
    )
    ch = DeliveryPointChannel.objects.create(idx="other-channel", name="Other Channel", default_language=lang)
    ch.languages.add(lang)
    return ch


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _points_url(channel_idx: str) -> str:
    return f"/api/deliverypoints/v2/{channel_idx}/points/"


def _nearby_url(channel_idx: str) -> str:
    return f"/api/deliverypoints/v2/{channel_idx}/points/nearby/"


def _point_detail_url(channel_idx: str, pk: int) -> str:
    return f"/api/deliverypoints/v2/{channel_idx}/points/{pk}/"


def _types_url(channel_idx: str) -> str:
    return f"/api/deliverypoints/v2/{channel_idx}/types/"


# ---------------------------------------------------------------------------
# TestPublicAccess
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicAccess:
    def test_public_endpoints_require_no_auth(self, api_client, channel):
        DeliveryPointFactory()
        response = api_client.get(_points_url(channel.idx))
        assert response.status_code == 200

    def test_public_types_no_auth(self, api_client, channel):
        DeliveryPointTypeFactory(is_active=True)
        response = api_client.get(_types_url(channel.idx))
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TestPublicPointList
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicPointList:
    def test_list_returns_active_only(self, api_client, channel):
        # Arrange
        active = DeliveryPointFactory(is_active=True)
        DeliveryPointFactory(is_active=False)

        # Act
        response = api_client.get(_points_url(channel.idx))

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert active.pk in result_ids
        assert len(result_ids) == 1

    def test_list_returns_global_and_channel_points(self, api_client, channel):
        # Arrange
        global_point = DeliveryPointFactory(is_active=True)
        channel_point = DeliveryPointFactory(channels=[channel], is_active=True)

        # Act
        response = api_client.get(_points_url(channel.idx))

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert global_point.pk in result_ids
        assert channel_point.pk in result_ids

    def test_list_excludes_other_channel_points(self, api_client, channel, other_channel):
        # Arrange
        DeliveryPointFactory(channels=[other_channel], is_active=True)

        # Act
        response = api_client.get(_points_url(channel.idx))

        # Assert
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_list_search(self, api_client, channel):
        # Arrange
        match = DeliveryPointFactory(city="Warsaw", is_active=True)
        DeliveryPointFactory(city="Krakow", is_active=True)

        # Act
        response = api_client.get(_points_url(channel.idx), {"search": "Warsaw"})

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert match.pk in result_ids
        assert len(result_ids) == 1

    def test_list_filter_by_type(self, api_client, channel):
        # Arrange
        inpost_type = DeliveryPointTypeFactory(code="inpost")
        dpd_type = DeliveryPointTypeFactory(code="dpd")
        inpost_point = DeliveryPointFactory(type=inpost_type, is_active=True)
        DeliveryPointFactory(type=dpd_type, is_active=True)

        # Act
        response = api_client.get(_points_url(channel.idx), {"type": "inpost"})

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert inpost_point.pk in result_ids
        assert len(result_ids) == 1

    def test_list_ordering(self, api_client, channel):
        # Arrange
        DeliveryPointFactory(city="Zielona Gora", is_active=True)
        DeliveryPointFactory(city="Bialystok", is_active=True)
        DeliveryPointFactory(city="Lodz", is_active=True)

        # Act
        response = api_client.get(_points_url(channel.idx), {"ordering": "city"})

        # Assert
        assert response.status_code == 200
        cities = [r["city"] for r in response.data["results"]]
        assert cities == sorted(cities)

    def test_list_paginated(self, api_client, channel):
        # Arrange
        DeliveryPointFactory.create_batch(3, is_active=True)

        # Act
        response = api_client.get(_points_url(channel.idx))

        # Assert
        assert response.status_code == 200
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data
        assert response.data["count"] == 3


# ---------------------------------------------------------------------------
# TestPublicPointRetrieve
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicPointRetrieve:
    def test_retrieve_active_point(self, api_client, channel):
        # Arrange
        point = DeliveryPointFactory(is_active=True)

        # Act
        response = api_client.get(_point_detail_url(channel.idx, point.pk))

        # Assert
        assert response.status_code == 200
        assert response.data["id"] == point.pk

    def test_retrieve_inactive_point_returns_404(self, api_client, channel):
        # Arrange
        point = DeliveryPointFactory(is_active=False)

        # Act
        response = api_client.get(_point_detail_url(channel.idx, point.pk))

        # Assert
        assert response.status_code == 404

    def test_retrieve_point_wrong_channel_returns_404(self, api_client, channel, other_channel):
        # Arrange
        point = DeliveryPointFactory(channels=[other_channel], is_active=True)

        # Act
        response = api_client.get(_point_detail_url(channel.idx, point.pk))

        # Assert
        assert response.status_code == 404

    def test_retrieve_global_point(self, api_client, channel, other_channel):
        # Arrange — no channels = global, accessible from any channel
        point = DeliveryPointFactory(is_active=True)

        # Act — retrieved via a different channel
        response = api_client.get(_point_detail_url(other_channel.idx, point.pk))

        # Assert
        assert response.status_code == 200
        assert response.data["id"] == point.pk


# ---------------------------------------------------------------------------
# TestPublicPointNearby
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicPointNearby:
    def test_nearby_returns_points_within_radius(self, api_client, channel):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        near = DeliveryPointFactory(
            type=dp_type, latitude=Decimal(str(POINT_1_KM[0])), longitude=Decimal(str(POINT_1_KM[1])), is_active=True
        )
        far = DeliveryPointFactory(
            type=dp_type, latitude=Decimal(str(POINT_50_KM[0])), longitude=Decimal(str(POINT_50_KM[1])), is_active=True
        )

        # Act
        response = api_client.get(
            _nearby_url(channel.idx), {"lat": WARSAW_CENTER[0], "lng": WARSAW_CENTER[1], "radius_km": 5}
        )

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert near.pk in result_ids
        assert far.pk not in result_ids

    def test_nearby_has_distance_field(self, api_client, channel):
        # Arrange
        DeliveryPointFactory(
            latitude=Decimal(str(POINT_1_KM[0])), longitude=Decimal(str(POINT_1_KM[1])), is_active=True
        )

        # Act
        response = api_client.get(
            _nearby_url(channel.idx), {"lat": WARSAW_CENTER[0], "lng": WARSAW_CENTER[1], "radius_km": 5}
        )

        # Assert
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1
        assert "distance" in response.data["results"][0]
        assert response.data["results"][0]["distance"] is not None

    def test_nearby_sorted_by_distance(self, api_client, channel):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(
            type=dp_type, latitude=Decimal(str(POINT_3_KM[0])), longitude=Decimal(str(POINT_3_KM[1])), is_active=True
        )
        DeliveryPointFactory(
            type=dp_type, latitude=Decimal(str(POINT_1_KM[0])), longitude=Decimal(str(POINT_1_KM[1])), is_active=True
        )

        # Act
        response = api_client.get(
            _nearby_url(channel.idx), {"lat": WARSAW_CENTER[0], "lng": WARSAW_CENTER[1], "radius_km": 5}
        )

        # Assert
        assert response.status_code == 200
        distances = [r["distance"] for r in response.data["results"]]
        assert distances == sorted(distances)

    def test_nearby_excludes_inactive(self, api_client, channel):
        # Arrange
        DeliveryPointFactory(
            latitude=Decimal(str(POINT_1_KM[0])), longitude=Decimal(str(POINT_1_KM[1])), is_active=False
        )

        # Act
        response = api_client.get(
            _nearby_url(channel.idx), {"lat": WARSAW_CENTER[0], "lng": WARSAW_CENTER[1], "radius_km": 5}
        )

        # Assert
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_nearby_missing_lat_returns_400(self, api_client, channel):
        # Act
        response = api_client.get(_nearby_url(channel.idx), {"lng": WARSAW_CENTER[1]})

        # Assert
        assert response.status_code == 400

    def test_nearby_missing_lng_returns_400(self, api_client, channel):
        # Act
        response = api_client.get(_nearby_url(channel.idx), {"lat": WARSAW_CENTER[0]})

        # Assert
        assert response.status_code == 400

    def test_nearby_invalid_lat_returns_400(self, api_client, channel):
        # Act
        response = api_client.get(_nearby_url(channel.idx), {"lat": "abc", "lng": WARSAW_CENTER[1]})

        # Assert
        assert response.status_code == 400

    def test_nearby_filter_by_type(self, api_client, channel):
        # Arrange
        inpost_type = DeliveryPointTypeFactory(code="inpost")
        dpd_type = DeliveryPointTypeFactory(code="dpd")
        inpost_point = DeliveryPointFactory(
            type=inpost_type,
            latitude=Decimal(str(POINT_1_KM[0])),
            longitude=Decimal(str(POINT_1_KM[1])),
            is_active=True,
        )
        DeliveryPointFactory(
            type=dpd_type, latitude=Decimal(str(POINT_1_KM[0])), longitude=Decimal(str(POINT_1_KM[1])), is_active=True
        )

        # Act
        response = api_client.get(
            _nearby_url(channel.idx),
            {"lat": WARSAW_CENTER[0], "lng": WARSAW_CENTER[1], "radius_km": 5, "type": "inpost"},
        )

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert inpost_point.pk in result_ids
        assert len(result_ids) == 1

    def test_nearby_respects_channel_scope(self, api_client, channel, other_channel):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        global_point = DeliveryPointFactory(
            type=dp_type, latitude=Decimal(str(POINT_1_KM[0])), longitude=Decimal(str(POINT_1_KM[1])), is_active=True
        )
        channel_point = DeliveryPointFactory(
            channels=[channel],
            type=dp_type,
            latitude=Decimal(str(POINT_1_KM[0])),
            longitude=Decimal(str(POINT_1_KM[1])),
            is_active=True,
        )
        other_point = DeliveryPointFactory(
            channels=[other_channel],
            type=dp_type,
            latitude=Decimal(str(POINT_1_KM[0])),
            longitude=Decimal(str(POINT_1_KM[1])),
            is_active=True,
        )

        # Act
        response = api_client.get(
            _nearby_url(channel.idx), {"lat": WARSAW_CENTER[0], "lng": WARSAW_CENTER[1], "radius_km": 5}
        )

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert global_point.pk in result_ids
        assert channel_point.pk in result_ids
        assert other_point.pk not in result_ids


# ---------------------------------------------------------------------------
# TestPublicTypeList
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicTypeList:
    def test_list_types_active_only(self, api_client, channel):
        # Arrange
        active = DeliveryPointTypeFactory(is_active=True)
        DeliveryPointTypeFactory(is_active=False)

        # Act
        response = api_client.get(_types_url(channel.idx))

        # Assert
        assert response.status_code == 200
        result_ids = [r["id"] for r in response.data["results"]]
        assert active.pk in result_ids
        assert len(result_ids) == 1

    def test_list_types_response_structure(self, api_client, channel):
        # Arrange
        DeliveryPointTypeFactory(code="inpost", name="InPost", is_carrier=True, is_active=True)

        # Act
        response = api_client.get(_types_url(channel.idx))

        # Assert
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        result = response.data["results"][0]
        assert "id" in result
        assert "code" in result
        assert "name" in result
        assert "is_carrier" in result
        assert "sort_order" in result

    def test_list_types_paginated(self, api_client, channel):
        # Arrange
        DeliveryPointTypeFactory.create_batch(3, is_active=True)

        # Act
        response = api_client.get(_types_url(channel.idx))

        # Assert
        assert response.status_code == 200
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert response.data["count"] == 3


# ---------------------------------------------------------------------------
# TestPublicLanguageFallback
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicLanguageFallback:
    def _make_language(self, iso2: str):
        lang, _ = Language.objects.get_or_create(
            iso2=iso2, defaults={"iso3": iso2 + "u", "name_en": iso2.upper(), "name_pl": iso2.upper()}
        )
        return lang

    def test_list_with_language_returns_translated_fields(self, api_client, channel):
        # Arrange
        point = DeliveryPointFactory(name="Base Name", hint="Base Hint", opening_hours="Mon-Fri", is_active=True)
        de = self._make_language("de")
        DeliveryPointT9N.objects.create(point=point, language=de, name="German Name", hint="Deutscher Hinweis")

        # Act
        response = api_client.get(_points_url(channel.idx), {"language": "de"})

        # Assert
        assert response.status_code == 200
        result = response.data["results"][0]
        assert result["name"] == "German Name"
        assert result["hint"] == "Deutscher Hinweis"
        assert result["opening_hours"] == "Mon-Fri"  # no T9N for opening_hours, base used

    def test_list_without_language_returns_base_fields(self, api_client, channel):
        # Arrange
        point = DeliveryPointFactory(name="Base Name", is_active=True)
        de = self._make_language("de")
        DeliveryPointT9N.objects.create(point=point, language=de, name="German Name")

        # Act
        response = api_client.get(_points_url(channel.idx))

        # Assert
        assert response.status_code == 200
        assert response.data["results"][0]["name"] == "Base Name"

    def test_language_fallback_to_channel_default(self, api_client, channel):
        # Arrange — channel default_language is "pl"
        point = DeliveryPointFactory(name="Base Name", is_active=True)
        pl = self._make_language("pl")
        DeliveryPointT9N.objects.create(point=point, language=pl, name="Polish Name")

        # Act — request "de" which doesn't exist, channel default is "pl"
        response = api_client.get(_points_url(channel.idx), {"language": "de"})

        # Assert — falls back to channel default language "pl"
        assert response.status_code == 200
        assert response.data["results"][0]["name"] == "Polish Name"

    def test_language_fallback_to_base_when_no_translation(self, api_client, channel):
        # Arrange — no translations exist
        DeliveryPointFactory(name="Base Name", is_active=True)

        # Act
        response = api_client.get(_points_url(channel.idx), {"language": "de"})

        # Assert — falls back to base fields
        assert response.status_code == 200
        assert response.data["results"][0]["name"] == "Base Name"

    def test_retrieve_with_language(self, api_client, channel):
        # Arrange
        point = DeliveryPointFactory(name="Base Name", is_active=True)
        de = self._make_language("de")
        DeliveryPointT9N.objects.create(point=point, language=de, name="German Name")

        # Act
        response = api_client.get(_point_detail_url(channel.idx, point.pk), {"language": "de"})

        # Assert
        assert response.status_code == 200
        assert response.data["name"] == "German Name"

    def test_nearby_with_language(self, api_client, channel):
        # Arrange
        point = DeliveryPointFactory(
            name="Base Name",
            latitude=Decimal(str(POINT_1_KM[0])),
            longitude=Decimal(str(POINT_1_KM[1])),
            is_active=True,
        )
        de = self._make_language("de")
        DeliveryPointT9N.objects.create(point=point, language=de, name="German Name")

        # Act
        response = api_client.get(
            _nearby_url(channel.idx),
            {"lat": WARSAW_CENTER[0], "lng": WARSAW_CENTER[1], "radius_km": 5, "language": "de"},
        )

        # Assert
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1
        assert response.data["results"][0]["name"] == "German Name"
