# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Delivery point type management service."""

from django.db.models import QuerySet

from django_deliverypoints.models import DeliveryPointType


def list_types(*, include_inactive: bool = False) -> QuerySet[DeliveryPointType]:
    """Return types. Active-only by default."""
    qs = DeliveryPointType.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs


def get_type(*, code: str) -> DeliveryPointType:
    """Get type by code. Raises ObjectDoesNotExist if not found."""
    return DeliveryPointType.objects.get(code=code)


def get_type_by_pk(*, pk: int) -> DeliveryPointType:
    """Get type by primary key. Raises ObjectDoesNotExist if not found."""
    return DeliveryPointType.objects.get(pk=pk)


def create_type(*, code: str, name: str, is_carrier: bool = False, **kwargs) -> DeliveryPointType:
    """Create a new type."""
    return DeliveryPointType.objects.create(code=code, name=name, is_carrier=is_carrier, **kwargs)


def update_type(*, pk: int, **kwargs) -> DeliveryPointType:
    """Update type fields. Returns updated instance.

    Raises ValueError if the type is a carrier (read-only).
    """
    dp_type = DeliveryPointType.objects.get(pk=pk)
    if dp_type.is_carrier:
        raise ValueError(f"Carrier type '{dp_type.code}' is read-only.")
    for field, value in kwargs.items():
        setattr(dp_type, field, value)
    dp_type.save()
    return dp_type


def delete_type(*, pk: int) -> None:
    """Delete type. Raises ProtectedError if points exist.

    Raises ValueError if the type is a carrier (read-only).
    """
    dp_type = DeliveryPointType.objects.get(pk=pk)
    if dp_type.is_carrier:
        raise ValueError(f"Carrier type '{dp_type.code}' is read-only.")
    dp_type.delete()
