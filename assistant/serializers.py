import json
from rest_framework import serializers
from assistant.models import Assistant, Chat, AssistantUser, AssistantChat, UsageBilling
from llm.models import Llm
from django.contrib.auth.models import User
from users.serializers import UserRelatedField
from llm.serializers import LlmRelatedField
from django.utils.timezone import now


class AssistantRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        serializer = AssistantSerializer(value)
        return serializer.data


class SimpleAssistantRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        serializer = SimpleAssistantSerializer(value)
        return serializer.data


class SimpleAssistantSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Assistant
        fields = ['id', 'uuid', 'assistant_id', 'name', 'model', 'avatar_url', 'assistant_status', 'assistant_level','auto_chat']

    def get_avatar_url(self, assistant):
        if assistant.avatar:
            return '/api{}'.format(assistant.avatar.url)


class AssistantSerializer(serializers.ModelSerializer):
    creator = UserRelatedField(queryset=User.objects.all(), required=True)
    avatar_url = serializers.SerializerMethodField()
    has_extra = serializers.SerializerMethodField()
    can_use = serializers.SerializerMethodField()
    llm = LlmRelatedField(queryset=Llm.objects.all(), required=True)

    class Meta:
        model = Assistant
        fields = ['id', 'uuid', 'assistant_id', 'name', 'model', 'description', 'instructions',
            'creator', 'service_provider', 'assistant_type', 'sync_time', 'assistant_status',
            'avatar_url', 'assistant_level', 'order_w', 'mode', 'gmt_create',
            'top_p', 'temperature', 'presence_penalty', 'frequency_penalty', 'max_tokens', 'message_limit',
            'tools', 'enable_search', 'llm','auto_chat', 'has_extra', 'can_use'
        ]


    def get_avatar_url(self, assistant):
        if assistant.avatar:
            return '/api/{}'.format(assistant.avatar.url)

    def get_can_use(self, assistant):
        request = self.context.get('request')
        if not request:
            return True
        user = request.user
        if user.is_superuser:
            return True
        now_time = now()
        if now_time <= user.extension.expires_time:
            if assistant.assistant_level == Assistant.ASSISTANT_LEVEL_FREE:
                return True

            assistant_user = AssistantUser.objects.filter(assistant=assistant, user=user).first()
            if assistant_user:
                return True

        return False

    def get_has_extra(self, assistant):
        if not assistant.tools:
            return False

        try:
            tools =  json.loads(assistant.tools)
        except Exception:
            return False

        qianchuan = False
        zhibo = False
        for item in tools:
            if item.get('name') in ['']:
                qianchuan = True
            if item.get('name') in []:
                zhibo = True 

        return {
            'qianchuan': qianchuan,
            'zhibo': zhibo,
        }

    def validate_tools(self, value):
        if not value:
            return value
        try:
            json.loads(value)
        except Exception:
            raise serializers.ValidationError("tools 字段必须为json格式") 
        return value


class ChatSerializer(serializers.ModelSerializer):
    user = UserRelatedField(queryset=User.objects.all(), required=True)
    assistant = AssistantRelatedField(queryset=Assistant.objects.all(), required=True)
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'uuid', 'name', 'thread_id', 'user', 'assistant', 'messages', 'is_group']

    def get_messages(self, chat):
        if chat.messages:
            return json.loads(chat.messages)
        return {}


class AssistantUserSerializer(serializers.ModelSerializer):
    user = UserRelatedField(queryset=User.objects.all(), required=True)
    assistant = SimpleAssistantRelatedField(queryset=Assistant.objects.all(), required=True)

    class Meta:
        model = AssistantUser
        fields = ['id', 'uuid', 'user', 'assistant']



class SimpleAssistantUserSerializer(serializers.ModelSerializer):
    assistant = SimpleAssistantRelatedField(queryset=Assistant.objects.all(), required=True)

    class Meta:
        model = AssistantUser
        fields = ['id', 'uuid', 'assistant']



class AssistantChatSerializer(serializers.ModelSerializer):
    # chat = UserRelatedField(queryset=Chat.objects.all(), required=True)
    assistant = SimpleAssistantRelatedField(queryset=Assistant.objects.all(), required=True)

    class Meta:
        model = AssistantChat
        fields = ['id', 'uuid', 'chat_id', 'assistant']



class UsageBillingSerializer(serializers.ModelSerializer):
    user = UserRelatedField(queryset=User.objects.all(), required=True)

    class Meta:
        model = UsageBilling
        fields = ['uuid', 'user', 'llm_name', 'prompt_tokens', 'completion_tokens', 'prompt_amount', 'completion_amount', 'currency_code', 'gmt_create']



