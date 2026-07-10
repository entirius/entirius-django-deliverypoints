# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pathlib

from django.core.management.base import BaseCommand, CommandError

from django_deliverypoints.services.import_service import import_csv


class Command(BaseCommand):
    help = "Import delivery points from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to CSV file")
        parser.add_argument("--type", dest="type_code", required=True, help="DeliveryPointType code")
        parser.add_argument(
            "--mode",
            required=True,
            choices=["incremental", "full"],
            help="Import mode: incremental (upsert) or full (replace all)",
        )
        parser.add_argument("--channel", dest="channel_idx", default=None, help="Channel idx (optional)")

    def handle(self, *args, **options):
        csv_path = pathlib.Path(options["file"])
        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        channel = None
        if options["channel_idx"]:
            from django_deliverypoints.models import DeliveryPointChannel

            try:
                channel = DeliveryPointChannel.objects.get(idx=options["channel_idx"])
            except DeliveryPointChannel.DoesNotExist as exc:
                raise CommandError(f"Channel not found: {options['channel_idx']}") from exc

        try:
            with csv_path.open(encoding="utf-8") as f:
                result = import_csv(
                    file=f, type_code=options["type_code"], mode=options["mode"], channel=channel, source="cli"
                )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"Import complete: created={result.created}, updated={result.updated}, disabled={result.disabled}"
        )
