# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Unit tests for delivery point models — constraints, __str__, cascade behavior."""

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from django_deliverypoints.models import (
    DeliveryPoint,
    DeliveryPointChannel,
    DeliveryPointT9N,
    DeliveryPointType,
    ImportLog,
)

from .factories import (
    DeliveryPointChannelFactory,
    DeliveryPointFactory,
    DeliveryPointT9NFactory,
    DeliveryPointTypeFactory,
    _get_or_create_language,
)


@pytest.mark.django_db
class TestDeliveryPointTypeModel:
    def test_str(self):
        dp_type = DeliveryPointTypeFactory(name="InPost", code="inpost")
        assert str(dp_type) == "InPost (inpost)"

    def test_code_unique(self):
        DeliveryPointTypeFactory(code="inpost")
        with pytest.raises(IntegrityError):
            DeliveryPointTypeFactory(code="inpost")

    def test_default_ordering_by_sort_order_then_name(self):
        t3 = DeliveryPointTypeFactory(sort_order=3, name="CCC")
        t1 = DeliveryPointTypeFactory(sort_order=1, name="AAA")
        t2 = DeliveryPointTypeFactory(sort_order=2, name="BBB")
        types = list(DeliveryPointType.objects.filter(pk__in=[t1.pk, t2.pk, t3.pk]))
        assert types == [t1, t2, t3]


@pytest.mark.django_db
class TestDeliveryPointModel:
    def test_str(self):
        point = DeliveryPointFactory(name="Warsaw Central", code="WAW-001")
        assert str(point) == "Warsaw Central (WAW-001)"

    def test_unique_type_code_constraint(self):
        dp_type = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=dp_type, code="SAME-CODE")
        with pytest.raises(IntegrityError):
            DeliveryPointFactory(type=dp_type, code="SAME-CODE")

    def test_same_code_different_type_allowed(self):
        type_a = DeliveryPointTypeFactory()
        type_b = DeliveryPointTypeFactory()
        DeliveryPointFactory(type=type_a, code="SAME-CODE")
        p2 = DeliveryPointFactory(type=type_b, code="SAME-CODE")
        assert p2.pk is not None

    def test_type_protect_on_delete(self):
        point = DeliveryPointFactory()
        dp_type = point.type
        with pytest.raises(ProtectedError):
            dp_type.delete()

    def test_channels_m2m_empty_means_global(self):
        point = DeliveryPointFactory()
        assert point.channels.count() == 0

    def test_channels_m2m_assignment(self):
        channel = DeliveryPointChannelFactory()
        point = DeliveryPointFactory(channels=[channel])
        assert channel in point.channels.all()

    def test_default_ordering_by_name(self):
        p3 = DeliveryPointFactory(name="Zebra")
        p1 = DeliveryPointFactory(name="Alpha")
        p2 = DeliveryPointFactory(name="Mike")
        points = list(DeliveryPoint.objects.filter(pk__in=[p1.pk, p2.pk, p3.pk]))
        assert points == [p1, p2, p3]


@pytest.mark.django_db
class TestDeliveryPointT9NModel:
    def test_str(self):
        t9n = DeliveryPointT9NFactory()
        result = str(t9n)
        assert t9n.point.code in result

    def test_unique_point_language_constraint(self):
        lang = _get_or_create_language("de")
        point = DeliveryPointFactory()
        DeliveryPointT9NFactory(point=point, language=lang)
        with pytest.raises(IntegrityError):
            DeliveryPointT9NFactory(point=point, language=lang)

    def test_cascade_on_point_delete(self):
        t9n = DeliveryPointT9NFactory()
        point_pk = t9n.point.pk
        t9n.point.delete()
        assert not DeliveryPointT9N.objects.filter(point_id=point_pk).exists()


@pytest.mark.django_db
class TestDeliveryPointChannelModel:
    def test_str(self):
        channel = DeliveryPointChannelFactory(idx="default-europe")
        assert str(channel) == "default-europe"

    def test_idx_unique(self):
        DeliveryPointChannelFactory(idx="test-channel")
        with pytest.raises(IntegrityError):
            DeliveryPointChannelFactory(idx="test-channel")

    def test_default_ordering_by_name(self):
        c3 = DeliveryPointChannelFactory(name="Zebra")
        c1 = DeliveryPointChannelFactory(name="Alpha")
        c2 = DeliveryPointChannelFactory(name="Mike")
        channels = list(DeliveryPointChannel.objects.filter(pk__in=[c1.pk, c2.pk, c3.pk]))
        assert channels == [c1, c2, c3]

    def test_default_language_set_null_on_delete(self):
        lang = _get_or_create_language("fr")
        channel = DeliveryPointChannelFactory(default_language=lang)
        lang.delete()
        channel.refresh_from_db()
        assert channel.default_language is None


@pytest.mark.django_db
class TestImportLogModel:
    def test_str(self):
        dp_type = DeliveryPointTypeFactory(code="inpost")
        log = ImportLog.objects.create(type=dp_type, mode="full", source="cli", entries=[])
        result = str(log)
        assert "inpost" in result
        assert "full" in result

    def test_cascade_on_type_delete(self):
        dp_type = DeliveryPointTypeFactory()
        ImportLog.objects.create(type=dp_type, mode="incremental", source="cli", entries=[])
        dp_type.delete()
        assert ImportLog.objects.count() == 0

    def test_channel_set_null_on_delete(self):
        dp_type = DeliveryPointTypeFactory()
        channel = DeliveryPointChannelFactory()
        log = ImportLog.objects.create(type=dp_type, mode="full", source="api", channel=channel, entries=[])
        channel.delete()
        log.refresh_from_db()
        assert log.channel is None
