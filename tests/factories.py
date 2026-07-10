# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import factory

from django_deliverypoints.models import DeliveryPoint, DeliveryPointChannel, DeliveryPointT9N, DeliveryPointType


class DeliveryPointTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeliveryPointType

    code = factory.Sequence(lambda n: f"type-{n}")
    name = factory.Sequence(lambda n: f"Type {n}")
    is_carrier = False
    is_active = True
    sort_order = factory.Sequence(lambda n: n)


class DeliveryPointChannelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeliveryPointChannel

    idx = factory.Sequence(lambda n: f"channel-{n}")
    name = factory.Sequence(lambda n: f"Channel {n}")


class DeliveryPointFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeliveryPoint

    type = factory.SubFactory(DeliveryPointTypeFactory)
    code = factory.Sequence(lambda n: f"POINT-{n:04d}")
    name = factory.Sequence(lambda n: f"Point {n}")
    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")
    street = factory.Faker("street_address")
    city = factory.Faker("city")
    post_code = factory.Faker("postcode")
    country = "PL"
    is_active = True

    @factory.post_generation
    def channels(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        self.channels.add(*extracted)


class DeliveryPointT9NFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeliveryPointT9N

    point = factory.SubFactory(DeliveryPointFactory)
    language = factory.LazyAttribute(lambda o: _get_or_create_language("de"))
    name = factory.Sequence(lambda n: f"Translated Point {n}")
    hint = ""
    opening_hours = ""


def _get_or_create_language(iso2: str):
    from django_regional.models import Language

    lang, _ = Language.objects.get_or_create(
        iso2=iso2, defaults={"iso3": iso2 + "u", "name_en": iso2.upper(), "name_pl": iso2.upper()}
    )
    return lang
