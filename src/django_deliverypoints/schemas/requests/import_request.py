# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for delivery point CSV imports."""

from pydantic import BaseModel, Field


class ImportRequest(BaseModel):
    type_code: str = Field(description="Delivery point type code to import into", examples=["inpost"])
    mode: str = Field(
        "incremental",
        description="Import mode: 'incremental' (upsert) or 'full' (replace all)",
        examples=["incremental"],
    )
    channel_idx: str | None = Field(
        None, description="Channel idx to scope the import (optional)", examples=["pl-main"]
    )
