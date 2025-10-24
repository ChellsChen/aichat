from django.db import models
from django.utils.timezone import now

# Create your models here.
from django.contrib.auth.models import User
from aichat.models import ModelBase
from llm.models import Llm


class Assistant(ModelBase):

    MODEL_SERVICE_PROVIDER_OPENAI = 'openai'
    MODEL_SERVICE_PROVIDER_ANTHROPIC = 'anthropic'
    MODEL_SERVICE_PROVIDER_DOUBAO = 'doubao'
    MODEL_SERVICE_PROVIDER_CHOICES = (
        (MODEL_SERVICE_PROVIDER_OPENAI, 'OpenAI'),
        (MODEL_SERVICE_PROVIDER_ANTHROPIC, 'Anthropic'),
        (MODEL_SERVICE_PROVIDER_DOUBAO, '豆包'),
    )

    ASSISTANT_TYPE_QIWU = 'qiwu'
    ASSISTANT_TYPE_CUSTOM = 'custom'
    ASSISTANT_TYPE_QIANCHUAN = 'qianchuan'
    ASSISTANT_TYPE_DOUYIN_OPERATION = 'douyin_operation'
    ASSISTANT_TYPE_XIAOHONGSHU = 'xiaohongshu'
    ASSISTANT_TYPE_TMALL = 'tmall'
    ASSISTANT_TYPE_DOUYIN_LIVEROOM = 'douyin_liveroom'
    ASSISTANT_TYPE_DOUYIN_SHORTVIDEO = 'douyin_shortvideo'
    ASSISTANT_TYPE_DOUYIN_HUASHU = 'douyin_huashu'

    ASSISTANT_TYPE_CHOICES = (
        (ASSISTANT_TYPE_QIWU, '其他'),
        (ASSISTANT_TYPE_CUSTOM, '用户自定义'),
        (ASSISTANT_TYPE_QIANCHUAN, '抖音-千川助手'),
        (ASSISTANT_TYPE_XIAOHONGSHU, '小红书助手'),
        (ASSISTANT_TYPE_TMALL, '天猫助手'),
        (ASSISTANT_TYPE_DOUYIN_LIVEROOM, '抖音-直播运营助手'),
        (ASSISTANT_TYPE_DOUYIN_SHORTVIDEO, '抖音-短视频运营助手'),
        (ASSISTANT_TYPE_DOUYIN_HUASHU, '抖音-话术助手')
    )


    ASSISTANT_MODE_CHAT = 'chat'
    ASSISTANT_MODE_ASSISTANT = 'assistant'
    ASSISTANT_MODE_BOT = 'bot'

    ASSISTANT_MODE_CHOICES = (
        (ASSISTANT_MODE_CHAT, 'chat-api'),
        (ASSISTANT_MODE_ASSISTANT, 'assistant-api'),
        (ASSISTANT_MODE_BOT, '豆包智能体')
    )

    ASSISTANT_LEVEL_FREE = 'free'
    ASSISTANT_LEVEL_PAY = 'pay'

    ASSISTANT_LEVEL_CHOICES = (
        (ASSISTANT_LEVEL_FREE, '免费助手'),
        (ASSISTANT_LEVEL_PAY, '付费助手'),
    )


    ASSISTANT_STATUS_ONLINE = 'online'
    ASSISTANT_STATUS_OFFLINE = 'offline'

    ASSISTANT_STATUS_CHOICES = (
        (ASSISTANT_STATUS_ONLINE, '在线'),
        (ASSISTANT_STATUS_OFFLINE, '已下线'),
    )
 
    name = models.CharField(max_length=256, help_text='助手名称')
    service_provider = models.CharField(max_length=256, choices=MODEL_SERVICE_PROVIDER_CHOICES, help_text='模型服务器提供商', default=MODEL_SERVICE_PROVIDER_OPENAI)
    model = models.CharField(max_length=256, blank=True, null=True, help_text='模型')
    llm = models.ForeignKey(Llm, on_delete=models.SET_NULL, blank=True, null=True, help_text='接入模型')
    assistant_id = models.CharField(max_length=256, help_text="助手ID", blank=True, null=True)
    description = models.CharField(max_length=512, help_text='功能介绍', blank=True, null=True)
    instructions = models.TextField(help_text='指令', blank=True, null=True)
    tools = models.TextField(help_text='tools', blank=True, null=True)
    tool_resources = models.TextField(help_text='tool_resources', blank=True, null=True)
    metadata = models.TextField(help_text='metadata', blank=True, null=True)
    temperature = models.FloatField(help_text='temperature', default=1, blank=True, null=True)
    top_p = models.FloatField(help_text='top_p', default=1, blank=True, null=True)
    response_format = models.CharField(max_length=256, help_text='响应格式', default='auto')
    assistant_type = models.CharField(max_length=256, choices=ASSISTANT_TYPE_CHOICES, default=ASSISTANT_TYPE_CUSTOM,  help_text='助手类别')
    mode = models.CharField(max_length=256, choices=ASSISTANT_MODE_CHOICES, default=ASSISTANT_MODE_ASSISTANT,  help_text='助手实现模式')
    avatar = models.ImageField(upload_to='avatar',  verbose_name='头像', default=None, blank=True, null=True, help_text='头像url')

    presence_penalty = models.FloatField(help_text='presence_penalty', default=0, blank=True, null=True)
    frequency_penalty = models.FloatField(help_text='frequency_penalty', default=0, blank=True, null=True)
    max_tokens = models.IntegerField(help_text='max_tokens', default=2048, blank=True, null=True)

    message_limit = models.IntegerField(help_text='附带历史消息数', default=5)

    user = models.ManyToManyField(to=User, blank=True, through='AssistantUser', editable=False)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, help_text='创建者', related_name='creator_assistants')

    sync_time = models.DateTimeField(blank=True, null=True, help_text='同步时间')
    assistant_status = models.CharField(max_length=256, help_text='助手状态', choices=ASSISTANT_STATUS_CHOICES, default=ASSISTANT_STATUS_ONLINE)
    assistant_level = models.CharField(max_length=256, help_text='助手级别', choices=ASSISTANT_LEVEL_CHOICES, default=ASSISTANT_LEVEL_PAY)
    order_w = models.IntegerField(help_text='排序权重', default=1)
    enable_search = models.BooleanField(help_text='启用联网搜索', default=False)
    auto_chat = models.BooleanField(help_text='是否自动对话', default=False)
    auto_chat_order = models.CharField(max_length=10, help_text='自动对话顺序', blank=True, null=True)

    def __str__(self):
        return '{}({})'.format(self.name, self.id)


    def save(self, *args, **kwargs):
        if self.llm:
            self.model = self.llm.name
            self.service_provider = self.llm.provider.value
        return super(Assistant, self).save(*args, **kwargs)


class AssistantUser(ModelBase):
    assistant = models.ForeignKey(Assistant, on_delete=models.CASCADE, db_constraint=False, help_text='助手', related_name='users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_constraint=False, help_text='用户', related_name='assistants')



class Chat(ModelBase):
    name = models.CharField(max_length=256, blank=True, null=True, help_text='对话名称')
    thread_id = models.CharField(max_length=256, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assistant = models.ForeignKey(Assistant, on_delete=models.CASCADE)
    messages = models.TextField(help_text='消息历史', blank=True, null=True)
    helper_sequence = models.TextField(help_text='助手顺序', blank=True, null=True)

    assistants = models.ManyToManyField(to=Assistant, blank=True, through='AssistantChat', editable=False, related_name='chatsets')

    is_group = models.BooleanField(help_text='是否群聊', default=False)


    def __str__(self):
        return '{}({}) | {} | {}'.format(self.name, self.id, self.assistant.name, self.user.username)


    class Meta:
        # ordering = ('-gmt_create', )
        ordering = ('-gmt_modify', )


class AssistantChat(ModelBase):
    assistant = models.ForeignKey(Assistant, on_delete=models.CASCADE, db_constraint=False, help_text='助手', related_name='assistant_chats')
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, db_constraint=False, help_text='聊天', related_name='assistant_chats')


class UsageBilling(ModelBase):
    CURRENCY_CNY = 'CNY'
    CURRENCY_USD = 'USD'

    currency_codes = (
        (CURRENCY_CNY, '人民币'),
        (CURRENCY_USD, '美元')
    )

    user = models.ForeignKey(User, on_delete=models.PROTECT, help_text='用户')
    llm = models.ForeignKey(Llm, on_delete=models.PROTECT, blank=True, null=True, help_text='模型')
    llm_name = models.CharField(max_length=256, blank=True, null=True, help_text='模型名称')
    prompt_tokens = models.IntegerField(help_text='输入tokens')
    completion_tokens = models.IntegerField(help_text='输出tokens')
    total_tokens = models.IntegerField(help_text='total tokens')

    prompt_amount = models.IntegerField(help_text='输入金额（单位为百万分之一元）')
    completion_amount = models.IntegerField(help_text='输出消费金额（单位为百万分之一元）')
    currency_code = models.CharField(max_length=32, choices=currency_codes, help_text='货币标志', default=CURRENCY_USD)
    billing_date = models.CharField(max_length=32, blank=True, null=True, help_text='账单日期')


    def save(self, *args, **kwargs):
        '''自动更新记录的账单日期'''
        if not self.gmt_create:
            self.billing_date = now().strftime('%Y-%m-%d')
        else:
            self.billing_date = self.gmt_create.strftime('%Y-%m-%d')
        return super(UsageBilling, self).save(*args, **kwargs)





