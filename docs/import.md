---
title: Import System
description: CSV import for delivery points with incremental and full sync modes.
---

Delivery points are imported from carrier-provided CSV files. The importer supports two modes and runs via management command or Admin API upload.

## Import Modes

| Mode | Behavior |
|------|----------|
| `incremental` | Upsert by `(type, code)`. Points absent from the CSV are left unchanged. |
| `full` | Upsert by `(type, code)`. Points of the given `--type` absent from CSV are set `is_active=False`. |

Full mode only deactivates points matching the `--type` argument — not all points in the database.

## CSV Format

Standard columns used by carrier feeds:

| Column | Description |
|--------|-------------|
| `delivery-point-x` | Longitude |
| `delivery-point-y` | Latitude |
| `delivery-point-name` | Display name |
| `delivery-point-code` | Point code (unique per type) |
| `delivery-point-type` | Type code (must exist in DeliveryPointType) |
| `delivery-point-address` | Street address |
| `delivery-point-city` | City |
| `delivery-point-postcode` | Postal code |
| `delivery-point-hint` | Optional customer hint text |

## Management Command

```bash
python manage.py import_deliverypoints \
  --file path/to/inpost.csv \
  --type inpost \
  --mode full
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--file` | Yes | Path to CSV file |
| `--type` | Yes | DeliveryPointType code to import |
| `--mode` | Yes | `incremental` or `full` |

## Import Flow

```
CSV file
  → import_deliverypoints command
    → import_service.import_from_csv(file, type_code, mode)
      → upsert each row: update_or_create(type=..., code=...)
      → if mode=full: set is_active=False for type's missing codes
```

The natural key for upsert is `(type, code)`. Never use `id` for import identity.

## Admin API Upload

The Admin API exposes a multipart upload endpoint:

```
POST /api/deliverypoints/v2/admin/import/
Content-Type: multipart/form-data

file=<csv>
type=inpost
mode=full
```

Requires JWT authentication and `IsAdminUser` permission.
