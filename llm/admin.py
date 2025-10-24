from django.contrib import admin
from llm.models import Llm, LlmProvider

# Register your models here.
@admin.register(Llm)
class LlmAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_display = ('name', 'value', 'provider')


@admin.register(LlmProvider)
class LlmProviderAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_display = ('name', 'value')