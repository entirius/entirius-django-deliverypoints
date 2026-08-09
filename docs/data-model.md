---
title: Data Model
description: DeliveryPointType and DeliveryPoint entities, constraints, and default fixtures.
---

## Entities

```
DeliveryPointType (global registry)
  ↑  FK
DeliveryPoint
  ↑  nullable FK
Channel (django_pim)
```

## DeliveryPointType

Global registry of point categories. Controls UI split: carrier types appear in checkout, custom types appear on map pages.

| Field | Type | Notes |
|-------|------|-------|
| `code` | CharField(64, unique) | Natural key: `inpost`, `dpd`, `showroom` |
| `name` | CharField(128) | Display name |
| `is_carrier` | BooleanField | `True` = carrier locker (checkout), `False` = custom location (map) |
| `is_active` | BooleanField | Soft-disable the entire type |
| `sort_order` | PositiveIntegerField | Display ordering |

### Default Types (fixture)

| code | name | is_carrier |
|------|------|-----------|
| `inpost` | InPost | True |
| `dpd` | DPD | True |
| `orlen` | Orlen | True |
| `poczta_polska` | Poczta Polska | True |
| `dhl` | DHL | True |
| `showroom` | Showroom | False |
| `retail_store` | Retail Store | False |

## DeliveryPoint

Individual pickup point. Carrier points are global (`channel=NULL`); custom points are channel-scoped.

| Field | Type | Notes |
|-------|------|-------|
| `type` | FK to DeliveryPointType | Required |
| `channel` | FK to Channel (nullable) | `NULL` = global, set = channel-specific |
| `code` | CharField(128) | Point identifier from carrier feed |
| `name` | CharField(256) | Display name |
| `lat` | DecimalField(10, 7) | Latitude, WGS84 |
| `lon` | DecimalField(10, 7) | Longitude, WGS84 |
| `street` | CharField(256) | |
| `city` | CharField(128) | |
| `state` | CharField(128, blank) | |
| `post_code` | CharField(16) | |
| `country` | CharField(2) | ISO 3166-1 alpha-2 |
| `phone` | CharField(32, blank) | |
| `email` | EmailField(blank) | |
| `website` | URLField(blank) | |
| `opening_hours` | JSONField (nullable) | Unstructured — validated in Pydantic schema |
| `hint` | TextField(blank) | Free-text note shown to customer |
| `is_active` | BooleanField | Soft-disable; full import mode sets this to False for missing points |

### Constraints

- `UniqueConstraint(type, code)` — natural key for import upsert
- `country` stores 2-char ISO codes; validated at Pydantic schema level, not model level
- `opening_hours` has no model-level schema enforcement — use Pydantic for request validation
