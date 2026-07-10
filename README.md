# django-deliverypoints

Delivery and pickup points management for Volkanos. Supports carrier pickup points (InPost, DPD, Orlen)
and custom location points (showrooms, retail stores).

## Features

- Delivery point type registry (carrier vs custom)
- Point CRUD with geo coordinates
- CSV import (incremental and full modes)
- Haversine-based nearby search
- Admin API (v2, JWT protected)
- Public API (v2, channel-scoped)

## Installation

```shell
pip install entirius-django-deliverypoints
```

Add the app to your project:

```python
INSTALLED_APPS = [
    ...
    "django_regional",
    "django_deliverypoints",
]
```

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django)
```

Development and agent instructions: [AGENTS.md](AGENTS.md).

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE).
