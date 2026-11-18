from django.contrib import admin

from .models import EntityFile, MediaFile, Thumbnail, Token, Quota, VerificationCode, WhiteList, BlackList
from .forms import WhiteListAdminForm, BlackListAdminForm

admin.site.register(EntityFile)
admin.site.register(MediaFile)
admin.site.register(Thumbnail)
admin.site.register(VerificationCode)


@admin.register(Quota)
class QuotaAdmin(admin.ModelAdmin):
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['used']


@admin.register(Token)
class CustomTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at']
    fields = ['user', 'expires', 'device', 'client', 'scope', 'key']


@admin.register(WhiteList)
class WhiteListAdmin(admin.ModelAdmin):
    form = WhiteListAdminForm


@admin.register(BlackList)
class BlackListAdmin(admin.ModelAdmin):
    form = BlackListAdminForm