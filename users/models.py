import datetime
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils.timezone import now

from aichat.models import ModelBase


# Create your models here.

class UserExtension(ModelBase):
    USER_LEVEL_DEFAULT = 'default'
    USER_LEVEL_VIP = 'vip'

    USER_LEVELS_CHOICES = (
        (USER_LEVEL_DEFAULT, '普通用户'),
        (USER_LEVEL_VIP, '付费用户'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='extension', help_text='关联账号')
    phone = models.CharField(max_length=16, null=True, blank=True, help_text='手机号')

    user_level = models.CharField(max_length=16, choices=USER_LEVELS_CHOICES, default=USER_LEVEL_DEFAULT, help_text='用户级别')
    expires_time = models.DateTimeField(null=True, blank=True, help_text='会员到期时间')


    qwen_key = models.CharField(max_length=256, null=True, blank=True, help_text='qwen_api_key')
    openai_key = models.CharField(max_length=256, null=True, blank=True, help_text='openai_api_key')
    doubao_key = models.CharField(max_length=256, null=True, blank=True, help_text='doubao_api_key')
    deepseek_key = models.CharField(max_length=256, null=True, blank=True, help_text='deepseek_api_key')
    claude_key = models.CharField(max_length=256, null=True, blank=True, help_text='claude_api_key')


@receiver(post_save, sender=User)
def create_user_extension(sender, instance, created,**kwargs):
    expires_time = now() + datetime.timedelta(days=settings.USER_FREE_USE_DAYS)
    if created:
        UserExtension.objects.create(user=instance, expires_time=expires_time)
    else:
        extension = UserExtension.objects.filter(user=instance).first()
        if not extension:
            UserExtension.objects.create(user=instance, expires_time=expires_time)
        else:
            instance.extension.save()