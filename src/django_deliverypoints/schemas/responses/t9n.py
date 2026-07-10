# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for delivery point translations."""

from pydantic import BaseModel, Field


class PointT9NResponse(BaseModel):
    language: str = Field(description="Language ISO2 code", examples=["de"])
    name: str = Field(description="Translated display name", examples=["InPost Paketstation Warschau"])
    hint: str = Field(description="Translated location hint", examples=["In der Naehe des Bahnhofs"])
    opening_hours: str = Field(description="Translated opening hours", examples=["Mo-Fr 8:00-20:00"])


class PointT9NListResponse(BaseModel):
    """Wrapper for list of translations — avoids drf-spectacular list[T] resolution issue."""

    results: list[PointT9NResponse] = Field(description="List of translations for a delivery point")
