from django.contrib import admin
from assistant.models import Assistant, Chat, AssistantUser, AssistantChat, UsageBilling

# Register your models here.
@admin.register(Assistant)
class AssistantAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_display = ('name', 'model', 'service_provider', 'assistant_type', 'assistant_level',  'assistant_status', 'sync_time', 'creator')


@admin.register(AssistantUser)
class AssistantUserAdmin(admin.ModelAdmin):
    list_display = ('assistant', 'user')


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('name', 'assistant_name', 'user', 'gmt_create', 'gmt_modify')


    @admin.display(description="assistant_id")
    def assistant_id(self, obj):
        return obj.assistant.assistant_id  if obj.assistant else ''

    @admin.display(description="assistant_name")
    def assistant_name(self, obj):
        return obj.assistant.name  if obj.assistant else ''




@admin.register(AssistantChat)
class AssistantChatAdmin(admin.ModelAdmin):
    list_display = ('assistant', 'chat')


@admin.register(UsageBilling)
class UsageBillingAdmin(admin.ModelAdmin):
    list_display = ('user', 'llm', 'prompt_tokens', 'completion_tokens', 'prompt_amount', 'completion_amount', 'currency_code')