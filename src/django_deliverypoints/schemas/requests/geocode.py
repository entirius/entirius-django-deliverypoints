# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request/response schemas for geocode search."""

from decimal import Decimal

from pydantic import BaseModel, Field


class GeocodeSearchRequest(BaseModel):
    query: str = Field(description="Address search query", min_length=3, examples=["ul. Marszalkowska 1, Warszawa"])
    country_bias: str | None = Field(None, description="Country ISO2 bias for results", examples=["PL"])
    limit: int = Field(5, description="Max number of results to return", ge=1, le=10)


class GeocodeSearchResult(BaseModel):
    formatted_address: str = Field(
        description="Full formatted address", examples=["Marszalkowska 1, 00-624 Warszawa, Poland"]
    )
    latitude: Decimal = Field(description="WGS84 latitude", examples=["52.2296756"])
    longitude: Decimal = Field(description="WGS84 longitude", examples=["21.0122287"])
    street: str = Field("", description="Street with number", examples=["Marszalkowska 1"])
    city: str = Field("", description="City name", examples=["Warszawa"])
    state: str = Field("", description="State or province", examples=["Mazowieckie"])
    post_code: str = Field("", description="Postal code", examples=["00-624"])
    country: str = Field("", description="ISO 3166-1 alpha-2 country code", examples=["PL"])
