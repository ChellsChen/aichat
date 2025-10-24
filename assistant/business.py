import json
import datetime
import base64
from django.utils.timezone import now
from django.contrib.auth.models import User
from django.core.cache import cache
from django.conf import settings

from openai import NotFoundError
from assistant.models import Assistant, AssistantUser
from llm.client import openai_api

def set_assitant_attr(assistant, item):
    assistant.name = item.get('name')
    assistant.model = item.get('model')
    assistant.description = item.get('description')
    assistant.instructions = item.get('instructions')
    assistant.tools = json.dumps(item.get('tools'))
    assistant.tool_resources = json.dumps(item.get('tool_resources'))
    assistant.metadata = json.dumps(item.get('metadata'))
    assistant.temperature = item.get('temperature')
    assistant.top_p = item.get('top_p')
    assistant.response_format = item.get('response_format')
    assistant.sync_time = now()
    assistant.assistant_status = Assistant.ASSISTANT_STATUS_ONLINE



def sync_all_assistants():
    resp = openai_api.list_assistant(limit=100)
    creator = User.objects.first()
    assistant_ids = []
    for item in resp.to_dict().get('data'):
        assistant_id = item.get('id')
        assistant_ids.append(assistant_id)
        assistant = Assistant.objects.filter(assistant_id=assistant_id).first()
        if not assistant:
            assistant = Assistant(
                assistant_id=assistant_id,
                creator=creator,
                assistant_type=Assistant.ASSISTANT_TYPE_QIWU
            )

        set_assitant_attr(assistant, item)
        assistant.save()

    offline_assistant = Assistant.objects.filter(mode=Assistant.ASSISTANT_MODE_ASSISTANT).exclude(assistant_id__in=assistant_ids).all()
    for item in offline_assistant:
        if item.assistant_id not in assistant_ids:
            item.assistant_status = Assistant.ASSISTANT_STATUS_OFFLINE
            item.save()

    return assistant_ids


def sync_one_assistant(assistant_id):
    assistant = Assistant.objects.filter(assistant_id=assistant_id).first()

    try:
        resp = openai_api.get_assistant(assistant_id)
    except NotFoundError:
        if assistant:
            assistant.assistant_status = Assistant.ASSISTANT_STATUS_OFFLINE
            assistant.save()
            return assistant_id

    if not assistant:
        creator = User.objects.first()
        assistant = Assistant(
            assistant_id=assistant_id,
            creator=creator,
            assistant_type=Assistant.ASSISTANT_TYPE_QIWU
        )

    item = resp.to_dict()
    set_assitant_attr(assistant, item)
    assistant.save()

    return assistant_id


def check_user_assistant(user, assistant):
    if user.is_superuser:
        return True, ''
    extension = user.extension

    if assistant.assistant_level == assistant.ASSISTANT_LEVEL_FREE:
        return True, ''

    now_time = now()
    if now_time > extension.expires_time:
        return False, '账号已过期'

    if extension.user_level == extension.USER_LEVEL_VIP:
        assistant_user = AssistantUser.objects.filter(user=user, assistant=assistant).first()
        if assistant_user:
            return True, ''

    id_str = str(assistant.id)
    if id_str in settings.USER_FREE_USE_ASSISTANT_IDS:
        return True, ''

    return False, '您的账号没有使用该助手的权限'


def check_free_user_usage(user, content, attachments):
    if user.is_superuser:
        return True, ''
    extension = user.extension
    if extension.user_level == extension.USER_LEVEL_VIP:
        return True, ''

    if attachments and len(attachments) > 0:
        return False, '您的账户不支持上传文件'

    now_date = datetime.datetime.now().strftime('%Y-%m-%d')
    key = 'user_usage_{}_{}_count'.format(now_date, user.id)
    usage_count = cache.get(key)
    if not usage_count:
        return True, ''

    max_num = settings.USER_FREE_USE_MSG_COUNT
    max_len = settings.USER_FREE_USE_MSG_LENGTH

    if usage_count > max_num:
        return False, '您的账户今日使用次数已达到上限'

    if content:
        for c in content:
            if c.get('type') == 'text':
                value = c.get('text')
                if len(value) >= max_len:
                    return False, '您的账户发送的消息长度不能超过 {} 个字符'.format(max_len)

    return True, ''


def check_and_cache_free_user_usage(user):
    if user.is_superuser:
        return True
    extension = user.extension
    if extension.user_level == extension.USER_LEVEL_VIP:
        return True

    now_date = datetime.datetime.now().strftime('%Y-%m-%d')
    key = 'user_usage_{}_{}_count'.format(now_date, user.id)
    usage_count = cache.get(key)
    if not usage_count:
        usage_count = 1

    usage_count = usage_count + 1
    cache.set(key, usage_count, timeout=60*60*24)

    return True


def encode_image(image_path, url_flag=True):
    with open(image_path, "rb") as fp:
        base64_image = base64.b64encode(fp.read()).decode('utf-8')
        if url_flag:
            url = f"data:image/jpeg;base64,{base64_image}"
            return url
        return base64_image


def link_assistant_user(assistants, user):
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