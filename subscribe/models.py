from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.dispatch import receiver
from django.db.models.signals import post_save

from aichat.models import ModelBase
from assistant.models import Assistant
from assistant.business import link_assistant_user

def validate_interval(value):
    if value < 0 or value > 100:
        raise ValidationError(_('%(value)s must be in the range [0, 100]'), params={'value': value},)


class SubscribePlan(ModelBase):
    name = models.CharField(max_length=256, help_text='商品名称')
    assistants = models.ManyToManyField(to=Assistant, blank=True, help_text='关联助手')
    price_per_month = models.IntegerField(help_text='每月价格(分)')
    description = models.TextField(help_text='介绍', blank=True, null=True)
    remark = models.TextField(help_text='备注', blank=True, null=True)


class SubscribePlanTime(ModelBase):
    timedelta_month = models.IntegerField(help_text='时间增量(按月算)')
    discount = models.IntegerField(help_text='折扣', default=100, blank=True, null=True, validators=[validate_interval, ])
    name = models.CharField(max_length=256, help_text='名称')
    badge_text = models.CharField(max_length=256, help_text='标注', blank=True, null=True)
    price = models.IntegerField(help_text='金额(分)', blank=True, null=True)

    class Meta:
        ordering = ('-timedelta_month', )

class SubscribePlanHistory(ModelBase):
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = (
        (STATUS_PENDING, '待支付'),
        (STATUS_COMPLETED, '支付完成'),
        (STATUS_CANCELED, '已取消')
    )

    trade_no = models.CharField(max_length=64, help_text='订单号', blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, help_text='订阅人', related_name='subscribe_plan_historys')
    subscribe_plan = models.ForeignKey(SubscribePlan, on_delete=models.SET_NULL, blank=True, null=True, help_text='订阅计划', related_name='subscribe_plan_historys')
    subscribe_plan_time = models.ForeignKey(SubscribePlanTime, on_delete=models.SET_NULL, blank=True, null=True, help_text='订阅时长', related_name='subscribe_plan_historys')
    name = models.CharField(max_length=256, help_text='商品名称')
    price = models.IntegerField(help_text='价格(分)')
    status = models.CharField(max_length=256, help_text='订单状态', choices=STATUS_CHOICES, default=STATUS_PENDING)
    gmt_completed = models.DateTimeField(blank=True, null=True, help_text='成交时间')
    pay_gmt_completed = models.DateTimeField(blank=True, null=True, help_text='支付交易时间')



@receiver(post_save, sender=SubscribePlan)
def post_save_subscribe_signal(sender, instance, created, **kwargs):
    if created:
        return
    assistants = instance.assistants.all()
    pay_history = SubscribePlanHistory.objects.filter(subscribe_plan=instance, status=SubscribePlanHistory.STATUS_COMPLETED).order_by('-id').all()
    userids = []
    for history in pay_history:
        user = history.user
        if user.id not in userids:
            link_assistant_user(assistants, user)
            userids.append(user.id)