# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for delivery points."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from django_deliverypoints.schemas.responses.t9n import PointT9NResponse
from django_deliverypoints.schemas.responses.type_response import DeliveryPointTypeResponse


class DeliveryPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key", examples=[1])
    type: DeliveryPointTypeResponse = Field(description="Delivery point type")
    channel_ids: list[int] = Field(
        default_factory=list, description="Channel primary keys (empty = global)", examples=[[1, 2]]
    )
    translations: list[PointT9NResponse] = Field(default_factory=list, description="Translations for this point")
    code: str = Field(description="Unique code within its type", examples=["POP-WAW-001"])
    name: str = Field(description="Display name", examples=["InPost Locker Warsaw Central"])
    latitude: Decimal | None = Field(description="Latitude coordinate", examples=[52.2297])
    longitude: Decimal | None = Field(description="Longitude coordinate", examples=[21.0122])
    street: str = Field(description="Street address", examples=["ul. Marszalkowska 1"])
    city: str = Field(description="City name", examples=["Warsaw"])
    state: str = Field(description="State or province", examples=["Masovian"])
    post_code: str = Field(description="Postal code", examples=["00-001"])
    country: str = Field(description="ISO 3166-1 alpha-2 country code", examples=["PL"])
    phone: str = Field(description="Contact phone number", examples=["+48 123 456 789"])
    email: str = Field(description="Contact email address", examples=["punkt@inpost.pl"])
    website: str = Field(description="Website URL", examples=["https://inpost.pl"])
    opening_hours: str = Field(description="Opening hours text", examples=["Mon-Fri 8:00-20:00"])
    hint: str = Field(description="Additional location hint or description", examples=["Near the main entrance"])
    is_active: bool = Field(description="Whether this point is active", examples=[True])
    created_at: datetime = Field(description="Creation timestamp", examples=["2024-01-01T00:00:00Z"])
    modified_at: datetime = Field(description="Last update timestamp", examples=["2024-01-01T00:00:00Z"])


class DeliveryPointListResponse(BaseModel):
    count: int = Field(description="Total number of delivery points", examples=[150])
    next: str | None = Field(
        None,
        description="URL of next page",
        examples=["http://localhost:8000/api/deliverypoints/v2/admin/points/?page=2"],
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[DeliveryPointResponse] = Field(description="List of delivery points")


class PublicPointResponse(BaseModel):
    """Public (read-only) response — no is_active, optional distance for nearby results."""

    id: int = Field(description="Point ID", examples=[1])
    type_code: str = Field(description="Type code", examples=["inpost"])
    type_name: str = Field(description="Type display name", examples=["InPost"])
    is_carrier: bool = Field(description="Whether this is a carrier type", examples=[True])
    code: str = Field(description="External point code", examples=["WAW01A"])
    name: str = Field(description="Display name", examples=["Warsaw Central"])
    latitude: Decimal | None = Field(None, description="WGS84 latitude", examples=[52.2297])
    longitude: Decimal | None = Field(None, description="WGS84 longitude", examples=[21.0122])
    street: str = Field(description="Street address", examples=["ul. Marszalkowska 1"])
    city: str = Field(description="City", examples=["Warszawa"])
    state: str = Field(description="State/province", examples=["Mazowieckie"])
    post_code: str = Field(description="Postal code", examples=["00-001"])
    country: str = Field(description="ISO 3166-1 alpha-2 country code", examples=["PL"])
    phone: str = Field(description="Phone number", examples=["+48 22 123 4567"])
    email: str = Field(description="Email address", examples=["info@example.com"])
    website: str = Field(description="Website URL", examples=["https://example.com"])
    opening_hours: str = Field(description="Operating hours", examples=["Mon-Fri 8:00-20:00"])
    hint: str = Field(description="Additional location info", examples=["Near the train station"])
    distance: float | None = Field(None, description="Distance in km (nearby search only)", examples=[1.5])


class PublicPointListResponse(BaseModel):
    count: int = Field(description="Total number of matching points", examples=[100])
    next: str | None = Field(
        None, description="URL of next page", examples=["http://localhost:8000/api/deliverypoints/v2/ch/points/?page=2"]
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[PublicPointResponse] = Field(description="List of delivery points")
