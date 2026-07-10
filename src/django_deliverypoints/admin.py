# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.contrib import admin

from django_deliverypoints.models import DeliveryPoint, DeliveryPointChannel, DeliveryPointT9N, DeliveryPointType
from django_deliverypoints.services import channel_service


class DeliveryPointTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_carrier", "is_active", "sort_order")
    list_filter = ("is_carrier", "is_active")
    search_fields = ["code", "name"]
    ordering = ("sort_order", "name")


class DeliveryPointT9NInline(admin.TabularInline):
    model = DeliveryPointT9N
    extra = 0


class DeliveryPointAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "city", "country", "is_active")
    list_filter = ("type", "is_active", "country")
    search_fields = ["code", "name", "city", "post_code", "street"]
    ordering = ("name",)
    autocomplete_fields = ["type"]
    filter_horizontal = ("channels",)
    inlines = [DeliveryPointT9NInline]


@admin.action(description="Sync channels from PIM")
def sync_channels_from_pim(modeladmin, request, queryset):
    count = channel_service.sync_channels_from_pim()
    modeladmin.message_user(request, f"Synced {count} channels from PIM.")


class DeliveryPointChannelAdmin(admin.ModelAdmin):
    list_display = ("idx", "name", "default_language")
    search_fields = ["idx", "name"]
    actions = [sync_channels_from_pim]


admin.site.register(DeliveryPointType, DeliveryPointTypeAdmin)
admin.site.register(DeliveryPoint, DeliveryPointAdmin)
admin.site.register(DeliveryPointChannel, DeliveryPointChannelAdmin)
admin.site.register(DeliveryPointT9N)
