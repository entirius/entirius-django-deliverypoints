---
title: "Delivery Points: Database Diagrams"
description: "Auto-generated ER diagrams for the Delivery Points module."
sidebar:
  badge:
    text: "Auto-gen"
    variant: "note"
---

:::caution[Auto-generated]
These diagrams are auto-generated from Django model introspection.
Do not edit. Run `make erd` in entirius-docker to regenerate.
:::

## Delivery Points

```d2 layout=elk
DeliveryPointType: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  code: varchar {constraint: unique}
  name: varchar
  is_carrier: bool
  is_active: bool
  sort_order: int
}

DeliveryPoint: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  channel_id: int {constraint: foreign_key}
  type_id: int {constraint: foreign_key}
  code: varchar
  name: varchar
  latitude: decimal
  longitude: decimal
  street: varchar
}

ImportLog: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  type_id: int {constraint: foreign_key}
  channel_id: int {constraint: foreign_key}
  mode: varchar
  created_count: int
  updated_count: int
  disabled_count: int
  entries: jsonb
}

Channel: {
  shape: sql_table
  style.fill: "#484B57"
  style.stroke: "#1A1C25"
  style.stroke-dash: 3
  style.font-color: "#9A9CAA"
  id: int {constraint: primary_key}
  label: "Channel (External: django_pim)"
}



DeliveryPoint.channel_id -> Channel.id: {style.stroke: "#484B57"}

DeliveryPoint.type_id -> DeliveryPointType.id: {style.stroke: "#00ACC1"}

ImportLog.type_id -> DeliveryPointType.id: {style.stroke: "#00ACC1"}

ImportLog.channel_id -> Channel.id: {style.stroke: "#484B57"}
```
