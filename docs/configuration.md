---
title: Configuration
description: All configurable settings for the Delivery Points module.
---

## Settings Reference

All settings are read from Django settings via `getattr()` with sensible defaults.
The module works out of the box with zero configuration.

| Setting | Default | Description |
|---------|---------|-------------|
| `DELIVERYPOINTS_SEARCH_RADIUS_KM` | `10` | Default radius (km) for the public nearby search endpoint |
| `DELIVERYPOINTS_IMPORT_BATCH_SIZE` | `1000` | Internal batch size hint for CSV import |
| `DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY` | `""` (empty) | Google Maps Geocoding API key. Empty = geocoding disabled |

## Geocoding

Set `DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY` to a valid Google Maps API key to enable:
- Auto-geocoding of CSV imports when coordinate columns are missing
- Address search in the CMS Points panel ("address lookup")

### Docker setup

The Docker environment reuses the existing `GOOGLE_MAPS_API` env var from `.env`:

```python
# docker/settings_local.py
DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY = os.environ.get("GOOGLE_MAPS_API", "")
```

Add your key to `.env`:

```
GOOGLE_MAPS_API=your-google-maps-api-key-here
```

### Behavior when disabled

- **Import**: CSV rows without coordinates are imported with `NULL` lat/lng. Warning logged at import start.
- **CMS**: Address search input is visible but disabled. Info notice explains how to enable it.
- **API**: `POST admin/geocode/search/` returns `{"available": false, "message": "..."}` with HTTP 200.

No errors, no failures. The module works exactly as it did before geocoding was added.
