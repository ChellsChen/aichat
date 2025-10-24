import datetime

from rest_framework import filters
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action


from django_filters.rest_framework import DjangoFilterBackend
from django.utils.timezone import make_aware
from django.db.models import Sum

from aichat.pagination import StandardResultsPagination
from assistant.models import UsageBilling
from assistant.serializers import UsageBillingSerializer


class UsageBillingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UsageBilling.objects.all()
    serializer_class = UsageBillingSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['uuid', 'llm_name', 'user__username']
    permission_classes = (IsAuthenticated, )

    def _make_aware_time(self, time_str):
        tt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        tt = make_aware(tt)
        return tt


    def get_queryset(self):
        params = self.request.query_params
        queryset = super().get_queryset()
        start_time = params.get('start_time')
        if start_time:
            start_time = self._make_aware_time(start_time)
            queryset = queryset.filter(gmt_create__gte=start_time)
        end_time = params.get('end_time')
        if end_time:
            end_time = self._make_aware_time(end_time)
            queryset = queryset.filter(gmt_create__lte=end_time)

        if self.request.user.is_superuser:
            if self.request.query_params.get('all'):
                return queryset
        return queryset.filter(user=self.request.user)

    def __validate_params(self, request):
        if not request.user.is_superuser:
            return False, 'no permission'
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        if not start_time or not end_time:
            return False, 'need start_time and end_time'

        start_time = '{} 00:00:00'.format(start_time)
        end_time = '{} 23:59:59'.format(end_time)

        start_time = self._make_aware_time(start_time)
        end_time = self._make_aware_time(end_time)

        currency_code = request.query_params.get('currency_code')
        if not currency_code:
            currency_code = 'USD'

        return True, (start_time, end_time, currency_code)

    def get_chart_queryset(self, request):
        ret, res = self.__validate_params(request)
        if not ret:
            return False, res
        start_time, end_time, currency_code = res

        queryset = UsageBilling.objects.filter(gmt_create__lte=end_time, gmt_create__gte=start_time, currency_code=currency_code)
        return True, queryset



    @action(methods=['get'], detail=False)
    def chart_total(self, request, *args, **kwargs):
        """总花费"""
        ret, res = self.get_chart_queryset(request)
        if not ret:
            return Response({'success': False, 'errorMessage': res})

        queryset = res.aggregate(
                sum_prompt_amount=Sum('prompt_amount'),
                sum_completion_amount=Sum('completion_amount')
            )

        return Response({'success': True, 'data': queryset})


    @action(methods=['get'], detail=False)
    def chart_user(self, request, *args, **kwargs):
        """各用户每日使用情况"""
        ret, res = self.get_chart_queryset(request)
        if not ret:
            return Response({'success': False, 'errorMessage': res})

        queryset = res.values('billing_date',  'user__username') \
            .annotate(
                sum_prompt_amount=Sum('prompt_amount'),
                sum_completion_amount=Sum('completion_amount'),
            )

        return Response({'success': True, 'data': queryset})

    @action(methods=['get'], detail=False)
    def chart_llm(self, request, *args, **kwargs):
        """各模型每日使用情况"""
        ret, res = self.get_chart_queryset(request)
        if not ret:
            return Response({'success': False, 'errorMessage': res})

        queryset = res.values('billing_date', 'llm_name') \
            .annotate(
                sum_prompt_amount=Sum('prompt_amount'),
                sum_completion_amount=Sum('completion_amount'),
            )

        return Response({'success': True, 'data': queryset})


    @action(methods=['get'], detail=False)
    def chart_user_order(self, request, *args, **kwargs):
        """用户使用排行榜"""
        ret, res = self.get_chart_queryset(request)
        if not ret:
            return Response({'success': False, 'errorMessage': res})

        queryset = res.values('user__username') \
            .annotate(
                sum_prompt_amount=Sum('prompt_amount'),
                sum_completion_amount=Sum('completion_amount'),
            )

        return Response({'success': True, 'data': queryset})
