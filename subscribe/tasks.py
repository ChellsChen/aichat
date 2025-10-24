import datetime
import logging

from celery import shared_task
from subscribe.models import SubscribePlanHistory
from django.utils.timezone import now
from subscribe.wxpay import get_wxpay
from subscribe.utils import validate_wxpay_success, process_pay_success


@shared_task
def clear_pending_timeout_history_task():
    clear_time = now() - datetime.timedelta(days=1)
    wxpay = get_wxpay()
    historys = SubscribePlanHistory.objects.filter(status=SubscribePlanHistory.STATUS_PENDING).all()
    for history in historys:
        ret, pay_data = validate_wxpay_success(history.trade_no)
        if ret:
            process_pay_success(history.trade_no, pay_data)
        else:
            if history.gmt_create < clear_time and history.gmt_completed is None:
                try:
                    logging.info('delete pending sub_history: {}'.format(history.trade_no))
                    history.delete()
                    if history.trade_no:
                        wxpay.close(history.trade_no)
                except Exception as e:
                    logging.exception('delete trade_no {} error: {}'.format(history.trade_no, e))
        
