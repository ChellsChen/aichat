import json
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.utils.timezone import now

from subscribe.wxpay import get_wxpay
from subscribe.models import SubscribePlanHistory
from assistant.models import AssistantUser
from users.models import UserExtension


def get_price_data(sub_plan, sub_time):
    if sub_time.price:
        price = sub_time.price
    else:
        discount = Decimal(sub_time.discount) / 100
        price = int(Decimal(sub_plan.price_per_month) * Decimal(sub_time.timedelta_month) * Decimal(discount))
    price_per_month = int(Decimal('%.2f' % (Decimal(price) / Decimal(sub_time.timedelta_month))))
    return (price, price_per_month)


def validate_wxpay_success(trade_no):
    wxpay = get_wxpay()
    code, message = wxpay.query(out_trade_no=trade_no)
    if code != 200:
        return False, None
    message = json.loads(message)
    if message.get('trade_state') == 'SUCCESS':
        return True, message
    return False, None


def process_pay_success(trade_no, pay_data):
    history = SubscribePlanHistory.objects.filter(trade_no=trade_no).first()
    if not history:
        return
    if history.status != SubscribePlanHistory.STATUS_PENDING:
        return

    sub_plan = history.subscribe_plan
    sub_time = history.subscribe_plan_time
    user = history.user

    assistants = sub_plan.assistants.all()
    ids = []
    for assistant in assistants:
        ids.append(assistant.id)
        assistant_user = AssistantUser.objects.filter(assistant=assistant, user=user).first()
        if not assistant_user:
            assistant_user = AssistantUser(assistant=assistant, user=user)
            assistant_user.save()

    assistant_users = AssistantUser.objects.filter(user=user).all()
    for assistant_user in assistant_users:
        if assistant_user.assistant.id not in ids:
            assistant_user.delete()


    time_now = now()
    begin_time = time_now
    extension = UserExtension.objects.filter(user=user).first()
    if extension.user_level == extension.USER_LEVEL_VIP:
        if extension.expires_time > time_now:
            begin_time = extension.expires_time

    expires_time = begin_time + relativedelta(months=sub_time.timedelta_month)
    extension.user_level = extension.USER_LEVEL_VIP
    extension.expires_time = expires_time
    extension.save()


    history.status = history.STATUS_COMPLETED
    history.gmt_completed = time_now
    history.pay_gmt_completed = pay_data.get('success_time')
    history.save()

    return history
