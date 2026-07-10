# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel


class DeliveryPointT9N(BaseModel):
    point = models.ForeignKey(
        "django_deliverypoints.DeliveryPoint", on_delete=models.CASCADE, related_name="translations"
    )
    language = models.ForeignKey("django_regional.Language", on_delete=models.CASCADE, related_name="+")
    name = models.CharField(max_length=200, blank=True, default="")
    hint = models.TextField(blank=True, default="")
    opening_hours = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["point", "language"], name="unique_point_language")]

    def __str__(self) -> str:
        return f"{self.point.code} [{self.language}]"
