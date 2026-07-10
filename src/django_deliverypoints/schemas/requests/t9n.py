# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for delivery point translations."""

from pydantic import BaseModel, Field


class PointT9NCreateRequest(BaseModel):
    language: str = Field(description="Language ISO2 code", examples=["de"], min_length=2, max_length=2)
    name: str = Field(
        "", description="Translated display name", examples=["InPost Paketstation Warschau"], max_length=200
    )
    hint: str = Field("", description="Translated location hint", examples=["In der Naehe des Bahnhofs"])
    opening_hours: str = Field(
        "", description="Translated opening hours", examples=["Mo-Fr 8:00-20:00"], max_length=255
    )


class PointT9NUpdateRequest(BaseModel):
    name: str | None = Field(
        None, description="Translated display name", examples=["InPost Paketstation Warschau"], max_length=200
    )
    hint: str | None = Field(None, description="Translated location hint", examples=["In der Naehe des Bahnhofs"])
    opening_hours: str | None = Field(
        None, description="Translated opening hours", examples=["Mo-Fr 8:00-20:00"], max_length=255
    )
