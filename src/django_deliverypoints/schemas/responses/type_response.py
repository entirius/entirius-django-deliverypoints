# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for delivery point types."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeliveryPointTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key", examples=[1])
    code: str = Field(description="Unique type code", examples=["inpost"])
    name: str = Field(description="Display name", examples=["InPost"])
    is_carrier: bool = Field(description="Whether this type represents a carrier pickup point", examples=[True])
    is_active: bool = Field(description="Whether this type is active", examples=[True])
    sort_order: int = Field(description="Sort order (lower = first)", examples=[1])
    created_at: datetime = Field(description="Creation timestamp", examples=["2024-01-01T00:00:00Z"])
    modified_at: datetime = Field(description="Last update timestamp", examples=["2024-01-01T00:00:00Z"])


class DeliveryPointTypeListResponse(BaseModel):
    count: int = Field(description="Total number of types", examples=[7])
    next: str | None = Field(
        None,
        description="URL of next page",
        examples=["http://localhost:8000/api/deliverypoints/v2/admin/types/?page=2"],
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[DeliveryPointTypeResponse] = Field(description="List of delivery point types")


class PublicTypeResponse(BaseModel):
    """Public (read-only) type response — no is_active (always true for public)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Type ID", examples=[1])
    code: str = Field(description="Unique type code", examples=["inpost"])
    name: str = Field(description="Display name", examples=["InPost"])
    is_carrier: bool = Field(description="Whether this is a carrier pickup type", examples=[True])
    sort_order: int = Field(description="Display order (lower = first)", examples=[1])


class PublicTypeListResponse(BaseModel):
    count: int = Field(description="Total number of active types", examples=[5])
    next: str | None = Field(
        None, description="URL of next page", examples=["http://localhost:8000/api/deliverypoints/v2/ch/types/?page=2"]
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[PublicTypeResponse] = Field(description="List of active delivery point types")
