from django.db import models

# Create your models here.
from aichat.models import ModelBase

class LlmProvider(ModelBase):
    name = models.CharField(max_length=256, help_text='厂商名称')
    value = models.CharField(max_length=256, help_text='厂商标识')

    api_key = models.CharField(max_length=256, help_text='api_key')
    base_url = models.CharField(max_length=256, help_text='base_url')
    project_id = models.CharField(max_length=256, null=True, blank=True, help_text='project_id')
    organization_id = models.CharField(max_length=256, null=True, blank=True, help_text='organization')
    remark = models.TextField(blank=True, null=True, help_text='备注')


    def __str__(self):
        return '{}({})'.format(self.name, self.value)


class Llm(ModelBase):
    PRICE_NUMBER_K = 'K'
    PRICE_NUMBER_M = 'M'

    PRICE_NUMBERS = (
        (PRICE_NUMBER_K, 'K'),
        (PRICE_NUMBER_M, 'M')
    )

    CURRENCY_CNY = 'CNY'
    CURRENCY_USD = 'USD'

    CURRENCY_CODES = (
        (CURRENCY_CNY, '人民币'),
        (CURRENCY_USD, '美元')
    )


    STATUS_INLINE = 'online'
    STATUS_OFFLINE = 'offline'

    STATUS_CHOICES = (
        (STATUS_INLINE, '在线'),
        (STATUS_OFFLINE, '已下线')
    ) 


    provider = models.ForeignKey(LlmProvider, on_delete=models.CASCADE, db_constraint=False, help_text='模型服务器提供商')
    name = models.CharField(max_length=256, help_text='模型名称')
    value = models.CharField(max_length=256, help_text='模型标识')
    remark = models.TextField(help_text='备注', blank=True, null=True)

    can_vision = models.BooleanField(help_text='可识别图片', default=False)
    can_toolcall = models.BooleanField(help_text='可工具调用', default=True)

    prompt_price = models.CharField(max_length=32, help_text='输入费用', default='10')
    completion_price = models.CharField(max_length=32, help_text='输出费用', default='10')
    currency_code = models.CharField(max_length=32, choices=CURRENCY_CODES, help_text='费用的货币标志', default=CURRENCY_USD)
    tokens_count = models.CharField(max_length=32, choices=PRICE_NUMBERS,  help_text='price值的tokens数量', default=PRICE_NUMBER_M)

    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_INLINE, help_text='模型状态')

    class Meta:
        ordering = ('id', )

    def __str__(self):
        return '{}({})'.format(self.name, self.value)