# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Service layer tests for django-deliverypoints."""

import io
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

from django_deliverypoints.models import DeliveryPointChannel, DeliveryPointT9N, ImportLog
from django_deliverypoints.services import channel_service
from django_deliverypoints.services.geo_service import find_nearby
from django_deliverypoints.services.geocoding_service import GeocodingResult, geocode_address, search_addresses
from django_deliverypoints.services.import_service import import_csv
from django_deliverypoints.services.point_service import (
    _generate_code,
    create_point,
    delete_point,
    get_point,
    list_points,
    resolve_translation,
    update_point,
)
from django_deliverypoints.services.type_service import create_type, delete_type, get_type, list_types, update_type

from .factories import DeliveryPointChannelFactory, DeliveryPointFactory, DeliveryPointTypeFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_channel(idx: str = "test-channel"):
    """Create a DeliveryPointChannel instance."""
    channel, _ = DeliveryPointChannel.objects.get_or_create(idx=idx, defaults={"name": f"Channel {idx}"})
    return channel


def _make_language(iso2: str):
    """Create a django_regional.Language instance."""
    from django_regional.models import Language

    lang, _ = Language.objects.get_or_create(
        iso2=iso2, defaults={"iso3": iso2 + "u", "name_en": iso2.upper(), "name_pl": iso2.upper()}
    )
    return lang


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


def _make_csv(*rows: str) -> io.StringIO:
    content = "\n".join([CSV_HEADER, *rows])
    return io.StringIO(content)


# CSV without coordinate columns
CSV_HEADER_NO_COORDS = (
    "delivery-point-name,delivery-point-code,delivery-point-type,"
    "delivery-point-address,delivery-point-city,delivery-point-postcode,delivery-point-hint"
)


def _csv_row_no_coords(
    name: str,
    code: str,
    type_code: str,
    address: str = "ul. Testowa 1",
    city: str = "Warszawa",
    postcode: str = "00-001",
    hint: str = "",
) -> str:
    return f"{name},{code},{type_code},{address},{city},{postcode},{hint}"


def _make_csv_no_coords(*rows: str) -> io.StringIO:
    content = "\n".join([CSV_HEADER_NO_COORDS, *rows])
    return io.StringIO(content)


# Mock Google Geocoding API response
MOCK_GOOGLE_RESPONSE = {
    "results": [
        {
            "formatted_address": "Marszalkowska 1, 00-624 Warszawa, Poland",
            "geometry": {"location": {"lat": 52.2296756, "lng": 21.0122287}},
            "address_components": [
                {"long_name": "1", "short_name": "1", "types": ["street_number"]},
                {"long_name": "Marszalkowska", "short_name": "Marszalkowska", "types": ["route"]},
                {"long_name": "Warszawa", "short_name": "Warszawa", "types": ["locality"]},
                {"long_name": "Mazowieckie", "short_name": "Mazowieckie", "types": ["administrative_area_level_1"]},
                {"long_name": "00-624", "short_name": "00-624", "types": ["postal_code"]},
                {"long_name": "Poland", "short_name": "PL", "types": ["country"]},
            ],
        }
    ],
    "status": "OK",
}


# ---------------------------------------------------------------------------
# type_service tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListTypes:
    def test_list_types_returns_active_only(self):
        # Arrange
        active = DeliveryPointTypeFactory(is_active=True)
        DeliveryPointTypeFactory(is_active=False)

        # Act
        result = list(list_types())

        # Assert
        assert active in result
        assert all(t.is_active for t in result)

    def test_list_types_returns_all_when_include_inactive(self):
        # Arrange
        active = DeliveryPointTypeFactory(is_active=True)
        inactive = DeliveryPointTypeFactory(is_active=False)

        # Act
        result = list(list_types(include_inactive=True))

        # Assert
        assert active in result
        assert inactive in result


@pytest.mark.django_db
class TestGetType:
    def test_get_type_by_code(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")

        # Act
        result = get_type(code="inpost")

        # Assert
        assert result.pk == dp_type.pk
        assert result.code == "inpost"

    def test_get_type_not_found_raises(self):
        # Act / Assert
        with pytest.raises(ObjectDoesNotExist):
            get_type(code="nonexistent")


@pytest.mark.django_db
class TestCreateType:
    def test_create_type(self):
        # Act
        result = create_type(code="test", name="Test", is_carrier=False)

        # Assert
        assert result.pk is not None
        assert result.code == "test"
        assert result.name == "Test"
        assert result.is_carrier is False

    def test_create_type_duplicate_code_raises(self):
        # Arrange
        DeliveryPointTypeFactory(code="dupe")

        # Act / Assert
        with pytest.raises((IntegrityError, Exception)):
            create_type(code="dupe", name="Duplicate")


@pytest.mark.django_db
class TestUpdateType:
    def test_update_type(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(name="Old Name")

        # Act
        result = update_type(pk=dp_type.pk, name="New Name")

        # Assert
        assert result.name == "New Name"
        assert result.pk == dp_type.pk


@pytest.mark.django_db
class TestDeleteType:
    def test_delete_type_without_points(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        pk = dp_type.pk

        # Act
        delete_type(pk=pk)

        # Assert — raises DoesNotExist if successfully deleted
        from django_deliverypoints.models import DeliveryPointType

        assert not DeliveryPointType.objects.filter(pk=pk).exists()

    def test_delete_type_with_points_raises(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type)

        # Act / Assert
        with pytest.raises(ProtectedError):
            delete_type(pk=dp_type.pk)


@pytest.mark.django_db
class TestCarrierTypeProtection:
    def test_update_carrier_type_raises(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(is_carrier=True, code="inpost")

        # Act / Assert
        with pytest.raises(ValueError, match="read-only"):
            update_type(pk=dp_type.pk, name="Changed")

    def test_delete_carrier_type_raises(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(is_carrier=True, code="dpd")

        # Act / Assert
        with pytest.raises(ValueError, match="read-only"):
            delete_type(pk=dp_type.pk)

    def test_update_custom_type_succeeds(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(is_carrier=False, name="Old")

        # Act
        result = update_type(pk=dp_type.pk, name="New")

        # Assert
        assert result.name == "New"

    def test_delete_custom_type_succeeds(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(is_carrier=False)
        pk = dp_type.pk

        # Act
        delete_type(pk=pk)

        # Assert
        from django_deliverypoints.models import DeliveryPointType

        assert not DeliveryPointType.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# point_service tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListPoints:
    def test_list_points_active_only(self):
        # Arrange
        active = DeliveryPointFactory(is_active=True)
        DeliveryPointFactory(is_active=False)

        # Act
        result = list(list_points())

        # Assert
        assert active in result
        assert all(p.is_active for p in result)

    def test_list_points_all(self):
        # Arrange
        active = DeliveryPointFactory(is_active=True)
        inactive = DeliveryPointFactory(is_active=False)

        # Act
        result = list(list_points(include_inactive=True))

        # Assert
        assert active in result
        assert inactive in result

    def test_list_points_filter_by_type(self):
        # Arrange
        inpost_type = DeliveryPointTypeFactory(code="inpost")
        dpd_type = DeliveryPointTypeFactory(code="dpd")
        inpost_point = DeliveryPointFactory(type=inpost_type)
        DeliveryPointFactory(type=dpd_type)

        # Act
        result = list(list_points(type_code="inpost"))

        # Assert
        assert inpost_point in result
        assert all(p.type.code == "inpost" for p in result)

    def test_list_points_global_only(self):
        # Arrange — points with no channels are global. When no channel_idx is given
        # and all_channels=False (default), only global points are returned.
        global_point = DeliveryPointFactory()

        # Act
        result = list(list_points())

        # Assert — global points (no channels) are included
        assert global_point in result

    def test_list_points_by_channel(self):
        # Arrange
        channel = _make_channel("svc-list-ch")
        channel_point = DeliveryPointFactory(channels=[channel])
        DeliveryPointFactory()  # global — excluded when filtering by channel

        # Act
        result = list(list_points(channel_idx=channel.idx))

        # Assert
        pks = [p.pk for p in result]
        assert channel_point.pk in pks

    def test_list_points_multi_channel(self):
        # Arrange — point assigned to two channels, queried from one
        ch1 = _make_channel("svc-mc1")
        ch2 = _make_channel("svc-mc2")
        point = DeliveryPointFactory(channels=[ch1, ch2])

        # Act
        result_ch1 = list(list_points(channel_idx=ch1.idx))
        result_ch2 = list(list_points(channel_idx=ch2.idx))

        # Assert — appears in both
        assert point in result_ch1
        assert point in result_ch2

    def test_list_points_search_by_name(self):
        # Arrange
        match = DeliveryPointFactory(name="WAW Central Station")
        DeliveryPointFactory(name="Krakow Point")

        # Act
        result = list(list_points(search="WAW"))

        # Assert
        assert match in result

    def test_list_points_search_by_code(self):
        # Arrange
        match = DeliveryPointFactory(code="WAW-001")
        DeliveryPointFactory(code="KRK-001")

        # Act
        result = list(list_points(search="WAW-001"))

        # Assert
        assert match in result

    def test_list_points_search_by_city(self):
        # Arrange
        match = DeliveryPointFactory(city="Warszawa")
        DeliveryPointFactory(city="Krakow")

        # Act
        result = list(list_points(search="Warszawa"))

        # Assert
        assert match in result

    def test_list_points_ordering(self):
        # Arrange
        DeliveryPointFactory(city="Zielona Gora")
        DeliveryPointFactory(city="Bialystok")
        DeliveryPointFactory(city="Lodz")

        # Act
        result = list(list_points(ordering="city"))

        # Assert — results are sorted by city ascending
        cities = [p.city for p in result]
        assert cities == sorted(cities)


@pytest.mark.django_db
class TestGetPoint:
    def test_get_point(self):
        # Arrange
        point = DeliveryPointFactory()

        # Act
        result = get_point(pk=point.pk)

        # Assert
        assert result.pk == point.pk

    def test_get_point_not_found_raises(self):
        # Act / Assert
        with pytest.raises(ObjectDoesNotExist):
            get_point(pk=999999)


@pytest.mark.django_db
class TestCreatePoint:
    def test_create_point(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")

        # Act
        result = create_point(type=dp_type, code="NEW01", name="New Point", city="Warszawa", post_code="00-001")

        # Assert
        assert result.pk is not None
        assert result.code == "NEW01"
        assert result.name == "New Point"
        assert result.type == dp_type

    def test_create_point_duplicate_type_code_raises(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, code="DUPE-001")

        # Act / Assert
        with pytest.raises((IntegrityError, Exception)):
            create_point(type=dp_type, code="DUPE-001", name="Duplicate")

    def test_create_point_with_channel_ids(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        channel = _make_channel("svc-ch-1")

        # Act
        result = create_point(type=dp_type, code="CH01", name="Channel Point", channel_ids=[channel.pk])

        # Assert
        assert list(result.channels.values_list("pk", flat=True)) == [channel.pk]

    def test_create_point_without_channels_is_global(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        result = create_point(type=dp_type, code="GLOB01", name="Global Point")

        # Assert
        assert result.channels.count() == 0

    def test_create_point_with_invalid_channel_raises(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act / Assert
        with pytest.raises(ValueError, match="not found"):
            create_point(type=dp_type, code="BAD01", name="Bad", channel_ids=[999999])


@pytest.mark.django_db
class TestUpdatePoint:
    def test_update_point(self):
        # Arrange
        point = DeliveryPointFactory(name="Old Name")

        # Act
        result = update_point(pk=point.pk, name="Updated")

        # Assert
        assert result.name == "Updated"
        assert result.pk == point.pk

    def test_update_point_set_channels(self):
        # Arrange
        point = DeliveryPointFactory()
        channel = _make_channel("svc-upd-ch")

        # Act
        result = update_point(pk=point.pk, channel_ids=[channel.pk])

        # Assert
        assert channel.pk in list(result.channels.values_list("pk", flat=True))

    def test_update_point_clear_channels(self):
        # Arrange
        channel = _make_channel("svc-clr-ch")
        point = DeliveryPointFactory(channels=[channel])

        # Act
        result = update_point(pk=point.pk, channel_ids=[])

        # Assert
        assert result.channels.count() == 0

    def test_update_point_null_channels_unchanged(self):
        # Arrange
        channel = _make_channel("svc-nul-ch")
        point = DeliveryPointFactory(channels=[channel])

        # Act — channel_ids=None means don't touch
        result = update_point(pk=point.pk, name="NewName")

        # Assert
        assert channel.pk in list(result.channels.values_list("pk", flat=True))


@pytest.mark.django_db
class TestDeletePoint:
    def test_delete_point(self):
        # Arrange
        point = DeliveryPointFactory()
        pk = point.pk

        # Act
        delete_point(pk=pk)

        # Assert
        from django_deliverypoints.models import DeliveryPoint

        assert not DeliveryPoint.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# geo_service tests
# ---------------------------------------------------------------------------

# Reference coordinates (WGS84)
WARSAW_CENTER = (52.2297, 21.0122)  # (lat, lng)
POINT_1_KM = (52.2350, 21.0200)  # ~1 km from center
POINT_3_KM = (52.2500, 21.0400)  # ~3 km from center
POINT_50_KM = (52.7000, 21.5000)  # ~50 km from center


@pytest.mark.django_db
class TestFindNearby:
    def test_find_nearby_returns_points_within_radius(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        near = DeliveryPointFactory(type=dp_type, latitude=POINT_1_KM[0], longitude=POINT_1_KM[1])
        also_near = DeliveryPointFactory(type=dp_type, latitude=POINT_3_KM[0], longitude=POINT_3_KM[1])
        far = DeliveryPointFactory(type=dp_type, latitude=POINT_50_KM[0], longitude=POINT_50_KM[1])

        # Act — search within 5 km of Warsaw center
        result = list(find_nearby(lat=WARSAW_CENTER[0], lng=WARSAW_CENTER[1], radius_km=5))

        # Assert
        pks = [p.pk for p in result]
        assert near.pk in pks
        assert also_near.pk in pks
        assert far.pk not in pks

    def test_find_nearby_returns_distance(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, latitude=POINT_1_KM[0], longitude=POINT_1_KM[1])

        # Act
        result = list(find_nearby(lat=WARSAW_CENTER[0], lng=WARSAW_CENTER[1], radius_km=5))

        # Assert — each result carries a distance attribute
        assert len(result) >= 1
        assert hasattr(result[0], "distance")
        assert result[0].distance > 0

    def test_find_nearby_sorted_by_distance(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, latitude=POINT_3_KM[0], longitude=POINT_3_KM[1])
        DeliveryPointFactory(type=dp_type, latitude=POINT_1_KM[0], longitude=POINT_1_KM[1])

        # Act
        result = list(find_nearby(lat=WARSAW_CENTER[0], lng=WARSAW_CENTER[1], radius_km=5))

        # Assert — ascending by distance
        distances = [p.distance for p in result]
        assert distances == sorted(distances)

    def test_find_nearby_excludes_inactive(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, latitude=POINT_1_KM[0], longitude=POINT_1_KM[1], is_active=False)

        # Act
        result = list(find_nearby(lat=WARSAW_CENTER[0], lng=WARSAW_CENTER[1], radius_km=5))

        # Assert
        assert result == []

    def test_find_nearby_no_results(self):
        # Arrange — DB is empty (no points created)

        # Act
        result = list(find_nearby(lat=WARSAW_CENTER[0], lng=WARSAW_CENTER[1], radius_km=5))

        # Assert
        assert result == []


# ---------------------------------------------------------------------------
# import_service tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestImportCsvIncremental:
    def test_import_csv_incremental_creates_new(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "Test Point 1", "TEST01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="incremental")

        # Assert
        from django_deliverypoints.models import DeliveryPoint

        assert DeliveryPoint.objects.filter(type=dp_type, code="TEST01").exists()

    def test_import_csv_incremental_updates_existing(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        existing = DeliveryPointFactory(type=dp_type, code="TEST01", name="Old Name")
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "New Name", "TEST01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="incremental")

        # Assert
        existing.refresh_from_db()
        assert existing.name == "New Name"

    def test_import_csv_incremental_leaves_missing(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        absent = DeliveryPointFactory(type=dp_type, code="ABSENT", is_active=True)
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "Test Point 1", "TEST01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="incremental")

        # Assert — absent point is untouched (still active)
        absent.refresh_from_db()
        assert absent.is_active is True


@pytest.mark.django_db
class TestImportCsvFull:
    def test_import_csv_full_creates_new(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "Test Point 1", "TEST01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="full")

        # Assert
        from django_deliverypoints.models import DeliveryPoint

        assert DeliveryPoint.objects.filter(type=dp_type, code="TEST01").exists()

    def test_import_csv_full_updates_existing(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        existing = DeliveryPointFactory(type=dp_type, code="TEST01", name="Old Name")
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "New Name", "TEST01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="full")

        # Assert
        existing.refresh_from_db()
        assert existing.name == "New Name"

    def test_import_csv_full_disables_missing(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        absent = DeliveryPointFactory(type=dp_type, code="ABSENT", is_active=True)
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "Test Point 1", "TEST01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="full")

        # Assert — missing point is disabled
        absent.refresh_from_db()
        assert absent.is_active is False


@pytest.mark.django_db
class TestImportLogging:
    def test_import_creates_log(self):
        # Arrange
        DeliveryPointTypeFactory(code="inpost")
        csv_file = _make_csv(
            _csv_row(21.0200, 52.2350, "Point A", "LOG01", "inpost"),
            _csv_row(21.0400, 52.2500, "Point B", "LOG02", "inpost"),
        )

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="incremental")

        # Assert
        log = ImportLog.objects.latest("created_at")
        assert log.created_count == 2
        assert log.updated_count == 0
        assert log.disabled_count == 0
        assert log.mode == "incremental"

    def test_import_log_tracks_changes(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        DeliveryPointFactory(type=dp_type, code="UPD01", name="Old Name")
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "New Name", "UPD01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="incremental")

        # Assert
        log = ImportLog.objects.latest("created_at")
        assert log.updated_count == 1
        updated_entry = next(e for e in log.entries if e["code"] == "UPD01")
        assert "changed_fields" in updated_entry
        assert "name" in updated_entry["changed_fields"]

    def test_import_log_source(self):
        # Arrange
        DeliveryPointTypeFactory(code="inpost")
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "Point", "SRC01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="incremental", source="api")

        # Assert
        log = ImportLog.objects.latest("created_at")
        assert log.source == "api"

    def test_import_full_logs_disabled(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        DeliveryPointFactory(type=dp_type, code="OLD01", is_active=True)
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "New Point", "NEW01", "inpost"))

        # Act
        import_csv(file=csv_file, type_code="inpost", mode="full")

        # Assert
        log = ImportLog.objects.latest("created_at")
        assert log.disabled_count >= 1
        disabled_entries = [e for e in log.entries if e["action"] == "disabled"]
        assert len(disabled_entries) >= 1
        assert any(e["code"] == "OLD01" for e in disabled_entries)


@pytest.mark.django_db
class TestImportCsvEdgeCases:
    def test_import_csv_empty_file_raises(self):
        # Arrange
        DeliveryPointTypeFactory(code="inpost")
        csv_file = io.StringIO("")

        # Act / Assert
        with pytest.raises(ValueError):
            import_csv(file=csv_file, type_code="inpost", mode="incremental")

    def test_import_csv_returns_result(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory(code="inpost")
        DeliveryPointFactory(type=dp_type, code="EXIST01", name="Old")
        csv_file = _make_csv(
            _csv_row(21.0200, 52.2350, "New Point", "NEW01", "inpost"),
            _csv_row(21.0400, 52.2500, "Updated", "EXIST01", "inpost"),
        )

        # Act
        result = import_csv(file=csv_file, type_code="inpost", mode="full")

        # Assert — result carries created/updated/disabled counts
        assert hasattr(result, "created")
        assert hasattr(result, "updated")
        assert hasattr(result, "disabled")
        assert result.created == 1
        assert result.updated == 1
        assert result.disabled == 0


# ---------------------------------------------------------------------------
# channel_service tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestChannelService:
    def test_list_channels(self):
        # Arrange
        DeliveryPointChannelFactory.create_batch(3)

        # Act
        result = list(channel_service.list_channels())

        # Assert
        assert len(result) == 3

    def test_get_channel(self):
        # Arrange
        ch = DeliveryPointChannelFactory(idx="test-get")

        # Act
        result = channel_service.get_channel("test-get")

        # Assert
        assert result.pk == ch.pk

    def test_get_channel_not_found_raises(self):
        # Act / Assert
        with pytest.raises(DeliveryPointChannel.DoesNotExist):
            channel_service.get_channel("nonexistent")

    def test_get_channels_by_pks(self):
        # Arrange
        ch1 = DeliveryPointChannelFactory()
        ch2 = DeliveryPointChannelFactory()

        # Act
        result = channel_service.get_channels_by_pks([ch1.pk, ch2.pk])

        # Assert
        assert len(result) == 2

    def test_get_channels_by_pks_missing_raises(self):
        # Act / Assert
        with pytest.raises(ValueError, match="not found"):
            channel_service.get_channels_by_pks([999999])


# ---------------------------------------------------------------------------
# translation fallback tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTranslationFallback:
    def test_no_language_returns_base_fields(self):
        # Arrange
        point = DeliveryPointFactory(name="Base Name", hint="Base Hint")

        # Act
        result = resolve_translation(point)

        # Assert
        assert result["name"] == "Base Name"
        assert result["hint"] == "Base Hint"

    def test_matching_language_returns_translation(self):
        # Arrange
        point = DeliveryPointFactory(name="Base Name")
        lang = _make_language("de")
        DeliveryPointT9N.objects.create(point=point, language=lang, name="German Name")

        # Act
        result = resolve_translation(point, language_iso2="de")

        # Assert
        assert result["name"] == "German Name"

    def test_missing_language_falls_back_to_channel_default(self):
        # Arrange
        point = DeliveryPointFactory(name="Base Name")
        en = _make_language("en")
        _make_language("de")
        channel = DeliveryPointChannelFactory(idx="fallback-ch", default_language=en)
        DeliveryPointT9N.objects.create(point=point, language=en, name="English Name")

        # Act — request "de" which doesn't exist, falls back to channel default "en"
        result = resolve_translation(point, channel=channel, language_iso2="de")

        # Assert
        assert result["name"] == "English Name"

    def test_missing_language_no_channel_default_returns_base(self):
        # Arrange
        point = DeliveryPointFactory(name="Base Name")

        # Act — no translation for "de", no channel
        result = resolve_translation(point, language_iso2="de")

        # Assert
        assert result["name"] == "Base Name"

    def test_translation_empty_field_falls_back_to_base(self):
        # Arrange
        point = DeliveryPointFactory(name="Base Name", hint="Base Hint")
        lang = _make_language("de")
        DeliveryPointT9N.objects.create(point=point, language=lang, name="German Name", hint="")

        # Act
        result = resolve_translation(point, language_iso2="de")

        # Assert
        assert result["name"] == "German Name"
        assert result["hint"] == "Base Hint"  # empty T9N falls back to base


# ---------------------------------------------------------------------------
# geocoding_service tests
# ---------------------------------------------------------------------------


class TestGeocodingServiceUnit:
    """Unit tests for geocoding_service — mock HTTP, no DB needed."""

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="test-key")
    @patch("django_deliverypoints.services.geocoding_service.requests.get")
    def test_geocode_address_parses_response(self, mock_get, _mock_key):
        # Arrange
        mock_get.return_value.json.return_value = MOCK_GOOGLE_RESPONSE
        mock_get.return_value.raise_for_status = lambda: None

        # Act
        result = geocode_address(street="Marszalkowska 1", city="Warszawa")

        # Assert
        assert result is not None
        assert result.latitude == Decimal("52.2296756")
        assert result.longitude == Decimal("21.0122287")
        assert result.city == "Warszawa"
        assert result.country == "PL"
        assert result.post_code == "00-624"
        assert "Marszalkowska" in result.street

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="test-key")
    @patch("django_deliverypoints.services.geocoding_service.requests.get")
    def test_geocode_address_empty_results_returns_none(self, mock_get, _mock_key):
        # Arrange
        mock_get.return_value.json.return_value = {"results": [], "status": "ZERO_RESULTS"}
        mock_get.return_value.raise_for_status = lambda: None

        # Act
        result = geocode_address(city="Nonexistent")

        # Assert
        assert result is None

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="")
    def test_geocode_address_no_api_key_returns_none(self, _mock_key):
        # Act
        result = geocode_address(city="Warszawa")

        # Assert
        assert result is None

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="test-key")
    @patch("django_deliverypoints.services.geocoding_service.requests.get")
    def test_geocode_address_http_error_returns_none(self, mock_get, _mock_key):
        # Arrange
        import requests as req

        mock_get.side_effect = req.RequestException("Network error")

        # Act
        result = geocode_address(city="Warszawa")

        # Assert
        assert result is None

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="test-key")
    @patch("django_deliverypoints.services.geocoding_service.requests.get")
    def test_search_addresses_returns_list(self, mock_get, _mock_key):
        # Arrange
        mock_get.return_value.json.return_value = MOCK_GOOGLE_RESPONSE
        mock_get.return_value.raise_for_status = lambda: None

        # Act
        results = search_addresses("Marszalkowska 1, Warszawa")

        # Assert
        assert len(results) == 1
        assert results[0].city == "Warszawa"
        assert results[0].latitude == Decimal("52.2296756")

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="")
    def test_search_addresses_no_api_key_returns_empty(self, _mock_key):
        # Act
        results = search_addresses("Marszalkowska 1")

        # Assert
        assert results == []

    @patch("django_deliverypoints.services.geocoding_service._get_api_key", return_value="test-key")
    def test_search_addresses_short_query_returns_empty(self, _mock_key):
        # Act
        results = search_addresses("ab")  # less than 3 chars

        # Assert
        assert results == []

    def test_geocode_address_empty_address_returns_none(self):
        # Act — no address parts at all
        result = geocode_address()

        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# _generate_code tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGenerateCode:
    def test_generate_code_basic(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        code = _generate_code("My Test Point", dp_type)

        # Assert
        assert code == "my-test-point"

    def test_generate_code_unicode(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act — Ł doesn't decompose via NFKD, so it gets stripped
        code = _generate_code("Punkt Odbioru Kraków", dp_type)

        # Assert
        assert code == "punkt-odbioru-krakow"

    def test_generate_code_dedup(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, code="test-point")

        # Act
        code = _generate_code("Test Point", dp_type)

        # Assert
        assert code == "test-point-2"

    def test_generate_code_dedup_multiple(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, code="test-point")
        DeliveryPointFactory(type=dp_type, code="test-point-2")

        # Act
        code = _generate_code("Test Point", dp_type)

        # Assert
        assert code == "test-point-3"

    def test_generate_code_empty_name(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        code = _generate_code("", dp_type)

        # Assert
        assert code == "point"

    def test_generate_code_special_chars(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act — & and # and ! are stripped, consecutive separators collapsed
        code = _generate_code("Test & Point #1!", dp_type)

        # Assert
        assert code == "test-point-1"


@pytest.mark.django_db
class TestCreatePointAutoCode:
    def test_create_point_without_code_generates_one(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        result = create_point(type=dp_type, name="Warsaw Showroom")

        # Assert
        assert result.code == "warsaw-showroom"
        assert result.pk is not None

    def test_create_point_with_code_uses_it(self):
        # Arrange
        dp_type = DeliveryPointTypeFactory()

        # Act
        result = create_point(type=dp_type, code="CUSTOM-CODE", name="Test")

        # Assert
        assert result.code == "CUSTOM-CODE"


# ---------------------------------------------------------------------------
# import with geocoding tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestImportWithGeocoding:
    @patch("django_deliverypoints.services.import_service.geocoding_service.is_available", return_value=True)
    @patch("django_deliverypoints.services.import_service.geocoding_service.geocode_address")
    def test_import_no_coords_with_geocoding(self, mock_geocode, _mock_avail):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        mock_geocode.return_value = GeocodingResult(
            latitude=Decimal("52.2297"), longitude=Decimal("21.0122"), formatted_address="Testowa 1, Warszawa"
        )
        csv_file = _make_csv_no_coords(_csv_row_no_coords("Test Point", "GEO-001", "showroom"))

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.geocoded == 1
        assert result.geocode_failed == 0
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="GEO-001")
        assert point.latitude is not None
        assert point.longitude is not None

    @patch("django_deliverypoints.services.import_service.geocoding_service.is_available", return_value=False)
    def test_import_no_coords_without_geocoding(self, _mock_avail):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        csv_file = _make_csv_no_coords(_csv_row_no_coords("Test Point", "NOCOORD-001", "showroom"))

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.geocoded == 0
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="NOCOORD-001")
        assert point.latitude is None
        assert point.longitude is None

    @patch("django_deliverypoints.services.import_service.geocoding_service.is_available", return_value=True)
    @patch("django_deliverypoints.services.import_service.geocoding_service.geocode_address", return_value=None)
    def test_import_no_coords_geocoding_fails(self, _mock_geocode, _mock_avail):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        csv_file = _make_csv_no_coords(_csv_row_no_coords("Bad Address Point", "FAIL-001", "showroom"))

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.geocoded == 0
        assert result.geocode_failed == 1
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="FAIL-001")
        assert point.latitude is None
        assert point.longitude is None

    def test_import_with_coords_columns_uses_csv_values(self):
        # Arrange — standard CSV with x/y columns, no geocoding needed
        DeliveryPointTypeFactory(code="inpost")
        csv_file = _make_csv(_csv_row(21.0200, 52.2350, "CSV Point", "CSV-001", "inpost"))

        # Act
        result = import_csv(file=csv_file, type_code="inpost", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.geocoded == 0
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="CSV-001")
        assert float(point.longitude) == 21.0200
        assert float(point.latitude) == 52.2350


# ---------------------------------------------------------------------------
# import validation tests
# ---------------------------------------------------------------------------

# CSV with country column
CSV_HEADER_WITH_COUNTRY = (
    "delivery-point-x,delivery-point-y,delivery-point-name,"
    "delivery-point-code,delivery-point-type,delivery-point-address,"
    "delivery-point-city,delivery-point-postcode,delivery-point-hint,delivery-point-country"
)


def _csv_row_with_country(
    x: float,
    y: float,
    name: str,
    code: str,
    type_code: str,
    address: str = "ul. Testowa 1",
    city: str = "Warszawa",
    postcode: str = "00-001",
    hint: str = "",
    country: str = "PL",
) -> str:
    return f"{x},{y},{name},{code},{type_code},{address},{city},{postcode},{hint},{country}"


def _make_csv_with_country(*rows: str) -> io.StringIO:
    content = "\n".join([CSV_HEADER_WITH_COUNTRY, *rows])
    return io.StringIO(content)


def _create_country(iso2: str, name_en: str = ""):
    """Create a django_regional.Country instance (bypasses save() block)."""
    from django_regional.models import Country

    if not Country.objects.filter(iso2=iso2).exists():
        Country.objects.bulk_create(
            [Country(iso2=iso2, iso3=iso2.lower() + "x", name_en=name_en or iso2, name_pl=name_en or iso2, prefix="")]
        )
    return Country.objects.get(iso2=iso2)


@pytest.mark.django_db
class TestImportValidation:
    def test_import_invalid_country_warns_and_clears(self):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        csv_file = _make_csv_with_country(
            _csv_row_with_country(21.0200, 52.2350, "Point A", "VAL-001", "showroom", country="XX")
        )

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.warnings == 1
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="VAL-001")
        assert point.country == ""

    def test_import_valid_country_uppercased(self):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        _create_country("PL", "Poland")
        csv_file = _make_csv_with_country(
            _csv_row_with_country(21.0200, 52.2350, "Point B", "VAL-002", "showroom", country="pl")
        )

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.warnings == 0
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="VAL-002")
        assert point.country == "PL"

    def test_import_out_of_range_latitude_warns_and_clears(self):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        csv_file = _make_csv(_csv_row(21.0200, 999.0, "Bad Lat Point", "VAL-003", "showroom"))

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.warnings == 1
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="VAL-003")
        assert point.latitude is None

    def test_import_out_of_range_longitude_warns_and_clears(self):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        csv_file = _make_csv(_csv_row(999.0, 52.2350, "Bad Lng Point", "VAL-004", "showroom"))

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.warnings == 1
        from django_deliverypoints.models import DeliveryPoint

        point = DeliveryPoint.objects.get(code="VAL-004")
        assert point.longitude is None

    def test_import_valid_data_no_warnings(self):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        _create_country("PL", "Poland")
        csv_file = _make_csv_with_country(
            _csv_row_with_country(21.0200, 52.2350, "Good Point", "VAL-005", "showroom", country="PL")
        )

        # Act
        result = import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        assert result.created == 1
        assert result.warnings == 0

    def test_import_log_contains_warnings(self):
        # Arrange
        DeliveryPointTypeFactory(code="showroom")
        csv_file = _make_csv_with_country(
            _csv_row_with_country(21.0200, 52.2350, "Warn Point", "VAL-006", "showroom", country="XX")
        )

        # Act
        import_csv(file=csv_file, type_code="showroom", mode="incremental")

        # Assert
        log = ImportLog.objects.latest("created_at")
        entry = next(e for e in log.entries if e["code"] == "VAL-006")
        assert "warnings" in entry
        assert any("country" in w.lower() for w in entry["warnings"])
