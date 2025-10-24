from rest_framework import serializers
from llm.models import Llm, LlmProvider



class LlmProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = LlmProvider
        fields = ['uuid', 'name', 'value']


class ProviderRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        serializer = LlmProviderSerializer(value)
        return serializer.data


class LlmSerializer(serializers.ModelSerializer):
    provider = ProviderRelatedField(queryset=LlmProvider.objects.all(), required=True)

    class Meta:
        model = Llm
        fields = ['uuid', 'name', 'value', 'provider', 'can_vision', 'can_toolcall']


class LlmRelatedField(serializers.RelatedField):
    def to_internal_value(self, data):
        llm = Llm.objects.filter(uuid=data).first()
        if llm:
            return llm

        raise serializers.ValidationError('illegal llm: {}'.format(data))

    def to_representation(self, value):
        serializer = LlmSerializer(value)
        return serializer.data