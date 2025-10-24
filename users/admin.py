from django.contrib import admin
from users.models import UserExtension
# Register your models here.
@admin.register(UserExtension)
class UserExtensionAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'user_level', 'expires_time')