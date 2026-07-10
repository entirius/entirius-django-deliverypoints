# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.conf import settings

DEBUG = getattr(settings, "DEBUG", False)

# Default geo search radius in km
DEFAULT_SEARCH_RADIUS_KM = getattr(settings, "DELIVERYPOINTS_SEARCH_RADIUS_KM", 10)

# Default import batch size
IMPORT_BATCH_SIZE = getattr(settings, "DELIVERYPOINTS_IMPORT_BATCH_SIZE", 1000)

# Google Maps Geocoding API key (empty = geocoding disabled)
GOOGLE_GEOCODING_API_KEY = getattr(settings, "DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY", "")
