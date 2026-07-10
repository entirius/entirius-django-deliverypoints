# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Channel management and sync service."""

import logging

from django.db.models import QuerySet

from django_deliverypoints.models import DeliveryPointChannel

logger = logging.getLogger(__name__)


def list_channels() -> QuerySet[DeliveryPointChannel]:
    """Return all delivery point channels."""
    return DeliveryPointChannel.objects.all()


def get_channel(idx: str) -> DeliveryPointChannel:
    """Get channel by idx. Raises DoesNotExist if not found."""
    return DeliveryPointChannel.objects.get(idx=idx)


def get_channel_or_none(idx: str) -> DeliveryPointChannel | None:
    """Get channel by idx with default_language pre-fetched, return None if not found."""
    try:
        return DeliveryPointChannel.objects.select_related("default_language").get(idx=idx)
    except DeliveryPointChannel.DoesNotExist:
        return None


def get_channels_by_pks(pks: list[int]) -> list[DeliveryPointChannel]:
    """Resolve channel PKs to DeliveryPointChannel instances."""
    channels = list(DeliveryPointChannel.objects.filter(pk__in=pks))
    if len(channels) != len(pks):
        found = {ch.pk for ch in channels}
        missing = [pk for pk in pks if pk not in found]
        raise ValueError(f"Channels not found: {missing}")
    return channels


def sync_channels_from_pim() -> int:
    """Sync DeliveryPointChannels from PIM Channel model.

    Creates or updates local channels keyed by idx.
    Returns count of synced channels.
    """
    try:
        from django_pim.models import Channel
    except ImportError:
        logger.info("django_pim not installed, skipping channel sync")
        return 0

    from django_regional.models import Language

    count = 0
    for pim_channel in Channel.objects.prefetch_related("languages").all():
        local_lang = None
        if pim_channel.default_language:
            local_lang = Language.objects.filter(iso2__iexact=pim_channel.default_language.iso2).first()

        dp_channel, _ = DeliveryPointChannel.objects.update_or_create(
            idx=pim_channel.idx, defaults={"name": pim_channel.name, "default_language": local_lang}
        )

        # Sync languages M2M
        pim_lang_iso2s = list(pim_channel.languages.values_list("iso2", flat=True))
        local_langs = Language.objects.filter(iso2__in=pim_lang_iso2s)
        dp_channel.languages.set(local_langs)

        count += 1

    return count
