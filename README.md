# entirius-django-deliverypoints

A Django module for delivery and pickup points in Entirius, the open-source modular ecommerce platform. It stores
carrier pickup points and a shop's own locations, imports them from CSV files and serves them to the storefront per
sales channel, with a nearby search.

[![PyPI](https://img.shields.io/pypi/v/entirius-django-deliverypoints.svg)](https://pypi.org/project/entirius-django-deliverypoints/)
[![Python](https://img.shields.io/pypi/pyversions/entirius-django-deliverypoints.svg)](https://pypi.org/project/entirius-django-deliverypoints/)
[![License: MPL-2.0](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](https://github.com/entirius/entirius-django-deliverypoints/blob/develop/LICENSE)

## What it does

- Keeps a registry of delivery point types: carrier networks and custom locations such as showrooms and retail
  stores.
- Stores points with geo coordinates, translations and sales channel scoping.
- Imports points from CSV files in incremental or full mode, with an audit log of every import.
- Finds points near a location with a Haversine distance search.
- Exposes an admin REST API (JWT) for the CMS and a public, channel-scoped REST API for the storefront.

## Installation

```shell
uv add entirius-django-deliverypoints
pip install entirius-django-deliverypoints
```

```python
INSTALLED_APPS = [
    ...
    "django_utils",
    "django_regional",
    "django_deliverypoints",
]

# urls.py
urlpatterns = [
    path("", include("django_deliverypoints.urls")),
]
```

No setting is required. Optional settings (`DELIVERYPOINTS_SEARCH_RADIUS_KM`, `DELIVERYPOINTS_IMPORT_BATCH_SIZE`,
`DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY`) are listed with their defaults in
https://github.com/entirius/entirius-django-deliverypoints/blob/develop/docs/configuration.md.

## Quick start

```python
from django_deliverypoints.services.point_service import public_nearby_points

points = public_nearby_points(channel_idx="default", lat=52.2297, lng=21.0122, radius_km=5)
```

Load points first: `python manage.py import_deliverypoints --file points.csv --type <type-code>`.

## Requirements

- Python 3.11 or newer, Django 5.0 or newer.
- Entirius packages pulled in: `entirius-django-utils`, `entirius-django-regional`.

## Documentation

- Module docs: https://github.com/entirius/entirius-django-deliverypoints/tree/develop/docs
- Entirius documentation: https://docs.entirius.com/
- Changelog: https://github.com/entirius/entirius-django-deliverypoints/blob/develop/CHANGELOG.md

## Part of Entirius

This module runs inside the Entirius backend service (Volkanos) and serves pickup points to the storefront checkout.

- Backend service: https://github.com/entirius/entirius-service-volkanos
- Docker harness: https://github.com/entirius/entirius-zeno
- Sibling modules: https://github.com/entirius/entirius-django-checkout,
  https://github.com/entirius/entirius-django-regional

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django, needs PostgreSQL via DATABASE_URL)
```

Development and agent instructions: https://github.com/entirius/entirius-django-deliverypoints/blob/develop/AGENTS.md

## License

Mozilla Public License 2.0 (MPL-2.0) — see https://github.com/entirius/entirius-django-deliverypoints/blob/develop/LICENSE.
