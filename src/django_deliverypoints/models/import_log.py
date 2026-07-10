# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel


class ImportLog(BaseModel):
    type = models.ForeignKey(
        "django_deliverypoints.DeliveryPointType", on_delete=models.CASCADE, related_name="import_logs"
    )
    mode = models.CharField(max_length=20)
    channel = models.ForeignKey(
        "django_deliverypoints.DeliveryPointChannel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_logs",
    )
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    disabled_count = models.PositiveIntegerField(default=0)
    entries = models.JSONField(default=list)
    source = models.CharField(max_length=10)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Import {self.type.code} ({self.mode}) at {self.created_at}"
