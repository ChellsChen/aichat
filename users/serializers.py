from rest_framework import serializers
from django.contrib.auth.models import User
from users.models import UserExtension



class UserLoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

class UserLoginSerializer(serializers.Serializer):
    status = serializers.CharField()
    type = serializers.CharField()
    currentAuthority = serializers.CharField()


# Serializers define the API representation.

class UserRelatedSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class UserExtensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserExtension
        fields = ['id', 'phone', 'expires_time', 'user_level']

class UserRelatedField(serializers.RelatedField):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = data['id']
        try:
            data = int(data)
        except:
            pass
        if isinstance(data, int):
            return User.objects.get(pk=data)

        raise serializers.ValidationError('illegal user: {}'.format(data))

    def to_representation(self, value):
        serializer = UserRelatedSerializer(value)
        return serializer.data


class UserExtensionRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        serializer = UserExtensionSerializer(value)
        return serializer.data

    def to_internal_value(self, data):
        #print('ahahahh')
        if isinstance(data, dict):
            data = data['id']
        try:
            data = int(data)
        except:
            pass
        if isinstance(data, int):
            return UserExtension.objects.get(pk=data)

        raise serializers.ValidationError('illegal extension: {}'.format(data))


from assistant.serializers import SimpleAssistantUserSerializer

class UserSerializer(serializers.ModelSerializer):
    extension = UserExtensionRelatedField(queryset=UserExtension.objects.all())
    assistants = SimpleAssistantUserSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'last_login', 'date_joined', 'is_superuser', 'is_active', 'extension', 'assistants']




class UserExtensionKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserExtension
        fields = ['id', 'qwen_key', 'openai_key', 'doubao_key', 'deepseek_key', 'claude_key']






