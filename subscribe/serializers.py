from decimal import Decimal
from rest_framework import serializers
from subscribe.models import SubscribePlan, SubscribePlanTime, SubscribePlanHistory
from django.contrib.auth.models import User
from users.serializers import UserRelatedField
from assistant.serializers import SimpleAssistantSerializer
from subscribe.utils import get_price_data


class SubscribePlanSerializer(serializers.ModelSerializer):
    assistants = SimpleAssistantSerializer(many=True)
    class Meta:
        model = SubscribePlan
        fields = ['id', 'uuid', 'name', 'price_per_month', 'description', 'remark', 'assistants']


class SubscribePlanTimeSerializer(serializers.ModelSerializer):
    alias_data = serializers.SerializerMethodField()

    class Meta:
        model = SubscribePlanTime
        fields = ['id', 'uuid', 'timedelta_month', 'discount', 'name', 'badge_text', 'alias_data']


    def get_alias_data(self, item):
        subscribe_plan = SubscribePlan.objects.first()
        price, price_per_month = get_price_data(subscribe_plan, item)
        price_per_month = Decimal(price_per_month) / Decimal(100)
        if price_per_month == 0:
            price_per_month = Decimal(0.01)
        data = {
            'price':  Decimal(price) / Decimal(100),
            'price_per_month': price_per_month
        }
        return data


class SubscribePlanHistorySerializer(serializers.ModelSerializer):
    user = UserRelatedField(queryset=User.objects.all(), required=True)

    class Meta:
        model = SubscribePlanHistory
        fields = ['id', 'uuid', 'user', 'name', 'price', 'trade_no', 'gmt_completed', 'status']