# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for delivery point types."""

from pydantic import BaseModel, Field


class DeliveryPointTypeCreateRequest(BaseModel):
    code: str = Field(description="Unique type code", examples=["inpost"], min_length=1, max_length=50)
    name: str = Field(description="Display name", examples=["InPost"], min_length=1, max_length=100)
    is_carrier: bool = Field(False, description="Whether this type represents a carrier pickup point", examples=[True])
    is_active: bool = Field(True, description="Whether this type is active", examples=[True])
    sort_order: int = Field(0, description="Sort order (lower = first)", examples=[1], ge=0)


class DeliveryPointTypeUpdateRequest(BaseModel):
    name: str | None = Field(None, description="Display name", examples=["InPost"], min_length=1, max_length=100)
    is_carrier: bool | None = Field(
        None, description="Whether this type represents a carrier pickup point", examples=[True]
    )
    is_active: bool | None = Field(None, description="Whether this type is active", examples=[True])
    sort_order: int | None = Field(None, description="Sort order (lower = first)", examples=[1], ge=0)
