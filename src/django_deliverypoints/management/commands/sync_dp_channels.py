# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand

from django_deliverypoints.services.channel_service import sync_channels_from_pim


class Command(BaseCommand):
    help = "Sync delivery point channels from PIM Channel model"

    def handle(self, *args, **options):
        count = sync_channels_from_pim()
        self.stdout.write(self.style.SUCCESS(f"Synced {count} channels from PIM."))
