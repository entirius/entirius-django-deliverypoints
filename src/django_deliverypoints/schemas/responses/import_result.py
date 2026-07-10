# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for CSV import results."""

from pydantic import BaseModel, Field


class ImportResultResponse(BaseModel):
    created: int = Field(description="Number of records created", examples=[120])
    updated: int = Field(description="Number of records updated", examples=[30])
    disabled: int = Field(description="Number of records disabled (full mode only)", examples=[5])
