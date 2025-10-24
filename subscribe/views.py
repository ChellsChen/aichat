import json
import logging
from django_filters.rest_framework import DjangoFilterBackend
from django.views.decorators.http import require_http_methods

from rest_framework import viewsets
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.http import JsonResponse, HttpResponseServerError, HttpResponseBadRequest
from django.utils.timezone import now

from drf_spectacular.utils import extend_schema
from aichat.pagination import StandardResultsPagination
from subscribe.models import SubscribePlan, SubscribePlanTime, SubscribePlanHistory
from subscribe.serializers import SubscribePlanSerializer, SubscribePlanTimeSerializer, SubscribePlanHistorySerializer
from subscribe.wxpay import get_wxpay
from wechatpayv3 import WeChatPayType
from subscribe.utils import get_price_data, validate_wxpay_success, process_pay_success

# Create your views here.

@extend_schema(description='wxpay_pay_action', request=None, responses=None)
@api_view(['POST',])
@permission_classes((AllowAny,))
def wxpay_pay_action(request):
    wxpay = get_wxpay()
    body = request.body
    headers = request.headers
    logging.info('wxpay request headers: {}'.format(headers))
    logging.info('wxpay request body: {}'.format(body))

    result = None
    try:
        result = wxpay.callback(headers, body)
        logging.info('wxpay get callback data: {}'.format(result))
    except Exception as e:
        logging.info('wxpay parse request body error: {}'.format(e))
    if result and result.get('event_type') == 'TRANSACTION.SUCCESS': 
        resource = result.get('resource')
        if resource.get('trade_state') == 'SUCCESS':
            trade_no = resource.get('out_trade_no')

            history = SubscribePlanHistory.objects.filter(trade_no=trade_no).first()
            if not history:
                return JsonResponse({'success': True})
            if history.status != history.STATUS_PENDING:
                return JsonResponse({'success': True, 'messages': '订单状态应为待支付'})

            ret, pay_data = validate_wxpay_success(trade_no)
            if not ret:
                return HttpResponseBadRequest('check pay error') 

            process_pay_success(trade_no, pay_data)
            return JsonResponse({'success': True})
    return HttpResponseBadRequest('wxpay callback data error') 


@extend_schema(description='completed_trade', request=None, responses=None)
@api_view(['POST',])
@permission_classes((IsAuthenticated,))
def completed_trade(request):
    trade_no = request.data.get('trade_no')
    if not request.user.is_superuser:
        return HttpResponseBadRequest('completed error')

    history = SubscribePlanHistory.objects.filter(trade_no=trade_no).first()
    if not history:
        return JsonResponse({'success': False})
    if history.status != history.STATUS_PENDING:
        return JsonResponse({'success': False, 'messages': '订单状态应为待支付'})

    ret, _ = validate_wxpay_success(trade_no)
    if not ret:
        return JsonResponse({'success': False, 'messages': '订单未支付成功'})

    process_pay_success(trade_no)

    return JsonResponse({'success': True})




@extend_schema(description='gen_pay_code', request=None, responses=None)
@api_view(['POST',])
@permission_classes((IsAuthenticated,))
def gen_pay_code(request):
    user = request.user
    sub_plan_uuid = request.data.get('sub_plan')
    sub_time_uuid = request.data.get('sub_time')

    sub_plan = SubscribePlan.objects.filter(uuid=sub_plan_uuid).first()
    if not sub_plan:
        return JsonResponse({'success': False, 'errorMessage':'sub_plan_uuid not exist'})
    sub_time = SubscribePlanTime.objects.filter(uuid=sub_time_uuid).first()
    if not sub_time:
        return JsonResponse({'success': False, 'errorMessage':'sub_time_uuid not exist'})


    name = '{}({})'.format(sub_plan.name, sub_time.name)

    price, price_per_month = get_price_data(sub_plan, sub_time)

    history = SubscribePlanHistory(
        user=user,
        subscribe_plan=sub_plan,
        subscribe_plan_time=sub_time,
        name=name,
        price=price
    )
    history.save()

    dd = now().strftime("%y%m%d%H%M%S")
    trade_no = '10{}{}'.format(dd, history.id)
    history.trade_no = trade_no
    history.save()

    wxpay = get_wxpay()
    code, message = wxpay.pay(
        description=name,
        out_trade_no=trade_no,
        amount={'total': price},
        pay_type=WeChatPayType.NATIVE
    )
    result = json.loads(message)
    if code not in range(200, 300):
        logging.error('发起微信支付错误:{}'.format(message))
        return JsonResponse({
            'success': False,
            'errorMessage': '发起微信支付错误'
        })

    result['trade_no'] = trade_no

    return JsonResponse({
        'data': result,
        'success': True
    })
    


class SubscribePlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SubscribePlan.objects.all()
    serializer_class = SubscribePlanSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    permission_classes = (IsAuthenticated, )


class SubscribePlanTimeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SubscribePlanTime.objects.all()
    serializer_class = SubscribePlanTimeSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    permission_classes = (IsAuthenticated, )


class SubscribePlanHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SubscribePlanHistory.objects.all()
    serializer_class = SubscribePlanHistorySerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    permission_classes = (IsAuthenticated, )
    filterset_fields = ['status', 'trade_no']


    def get_queryset(self):
        trade_no = self.request.query_params.get('trade_no')
        if trade_no and self.request.query_params.get('checked') == 'checked':
            ret, pay_data = validate_wxpay_success(trade_no)
            if ret:
                process_pay_success(trade_no, pay_data)
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            if self.request.query_params.get('all'):
                return queryset
        return queryset.filter(user=self.request.user)




