# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for delivery points."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class DeliveryPointCreateRequest(BaseModel):
    type_id: int = Field(description="DeliveryPointType primary key", examples=[1])
    code: str | None = Field(
        None,
        description="Unique code for this point within its type. Auto-generated from name if not provided.",
        examples=["POP-WAW-001"],
        max_length=100,
    )
    name: str = Field(
        description="Display name of the delivery point",
        examples=["InPost Locker Warsaw Central"],
        min_length=1,
        max_length=200,
    )
    latitude: Decimal | None = Field(None, description="Latitude coordinate", examples=[52.2297])
    longitude: Decimal | None = Field(None, description="Longitude coordinate", examples=[21.0122])
    street: str = Field("", description="Street address", examples=["ul. Marszalkowska 1"])
    city: str = Field("", description="City name", examples=["Warsaw"])
    state: str = Field("", description="State or province", examples=["Masovian"])
    post_code: str = Field("", description="Postal code", examples=["00-001"])
    country: str = Field("", description="ISO 3166-1 alpha-2 country code", examples=["PL"], max_length=2)
    phone: str = Field("", description="Contact phone number", examples=["+48 123 456 789"])
    email: str = Field("", description="Contact email address", examples=["punkt@inpost.pl"])
    website: str = Field("", description="Website URL", examples=["https://inpost.pl"])
    opening_hours: str = Field("", description="Opening hours text", examples=["Mon-Fri 8:00-20:00"])
    hint: str = Field("", description="Additional location hint or description", examples=["Near the main entrance"])
    is_active: bool = Field(True, description="Whether this point is active", examples=[True])
    channel_ids: list[int] = Field(
        default_factory=list, description="Channel primary keys (empty = global point)", examples=[[1, 2]]
    )

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        if not v:
            return v
        v = v.upper()
        from django_regional.models import Country

        if not Country.objects.filter(iso2=v).exists():
            raise ValueError(f"Invalid ISO 3166-1 country code: {v}")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class DeliveryPointUpdateRequest(BaseModel):
    name: str | None = Field(
        None,
        description="Display name of the delivery point",
        examples=["InPost Locker Warsaw Central"],
        min_length=1,
        max_length=200,
    )
    latitude: Decimal | None = Field(None, description="Latitude coordinate", examples=[52.2297])
    longitude: Decimal | None = Field(None, description="Longitude coordinate", examples=[21.0122])
    street: str | None = Field(None, description="Street address", examples=["ul. Marszalkowska 1"])
    city: str | None = Field(None, description="City name", examples=["Warsaw"])
    state: str | None = Field(None, description="State or province", examples=["Masovian"])
    post_code: str | None = Field(None, description="Postal code", examples=["00-001"])
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code", examples=["PL"], max_length=2)
    phone: str | None = Field(None, description="Contact phone number", examples=["+48 123 456 789"])
    email: str | None = Field(None, description="Contact email address", examples=["punkt@inpost.pl"])
    website: str | None = Field(None, description="Website URL", examples=["https://inpost.pl"])
    opening_hours: str | None = Field(None, description="Opening hours text", examples=["Mon-Fri 8:00-20:00"])
    hint: str | None = Field(
        None, description="Additional location hint or description", examples=["Near the main entrance"]
    )
    is_active: bool | None = Field(None, description="Whether this point is active", examples=[True])
    channel_ids: list[int] | None = Field(
        None, description="Channel primary keys (empty list = global, null = unchanged)", examples=[[1, 2]]
    )

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        if not v:
            return v
        v = v.upper()
        from django_regional.models import Country

        if not Country.objects.filter(iso2=v).exists():
            raise ValueError(f"Invalid ISO 3166-1 country code: {v}")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v
