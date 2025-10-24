import datetime
from django.db.models import Sum
from django.utils.timezone import now, make_aware

from assistant.models import UsageBilling

def sync_usage_billing_date(date=None):
    if date is None:
        date = now().strftime('%Y-%m-%d')
    start_time = '{} 00:00:00'.format(date)
    end_time = '{} 23:59:59'.format(date)

    start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    start_time = make_aware(start_time)

    end_time = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    end_time = make_aware(end_time)

    datas = UsageBilling.objects.filter(gmt_create__lte=end_time, gmt_create__gte=start_time) \
        .values('user__username', 'llm_name', 'currency_code') \
        .annotate(
            sum_prompt_amount=Sum('prompt_amount'),
            sum_completion_amount=Sum('completion_amount'),
        )
    for item in datas:
        print(item)



def sync_billing_date():
    datas = UsageBilling.objects.all()
    for item in datas:
        print(item.billing_date)
        item.save()