# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel


class DeliveryPoint(BaseModel):
    channels = models.ManyToManyField(
        "django_deliverypoints.DeliveryPointChannel", blank=True, related_name="delivery_points"
    )
    type = models.ForeignKey("django_deliverypoints.DeliveryPointType", on_delete=models.PROTECT, related_name="points")
    code = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    street = models.CharField(max_length=200, blank=True, default="")
    city = models.CharField(max_length=100, db_index=True, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    post_code = models.CharField(max_length=20, db_index=True, blank=True, default="")
    country = models.CharField(max_length=2, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    opening_hours = models.CharField(max_length=255, blank=True, default="")
    hint = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["type", "code"], name="unique_type_code")]
        indexes = [
            models.Index(fields=["type", "is_active"], name="idx_type_active"),
            models.Index(fields=["latitude", "longitude"], name="idx_coordinates"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
