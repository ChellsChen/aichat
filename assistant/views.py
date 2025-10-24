import os
import imghdr
import time
import json
import logging
from contextlib import nullcontext
from datetime import datetime, timedelta
from operator import truediv
from xmlrpc.client import Boolean

import redis
from apscheduler.triggers.date import DateTrigger
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseBadRequest, StreamingHttpResponse
from django.shortcuts import HttpResponse
from django.conf import settings
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.db.models import Q
from django.core.files.base import ContentFile

from rest_framework import filters
from rest_framework import viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
# from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView


from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from openai import NotFoundError

# from aichat.permissions import ModelCRUDPermission
from aichat.pagination import StandardResultsPagination


from assistant.models import Assistant, Chat, AssistantUser, AssistantChat, UsageBilling
from assistant.serializers import AssistantSerializer, ChatSerializer, AssistantUserSerializer, AssistantChatSerializer, SimpleAssistantSerializer, UsageBillingSerializer

from assistant.business import (
    sync_one_assistant,
    sync_all_assistants,
    check_user_assistant,
    check_free_user_usage,
    check_and_cache_free_user_usage
)

from llm.client import openai_api
from llm.models import Llm
# from assistant.chat import ChatRunTime
from assistant.chat import get_runtime
from utils.redis import RedisUtil

IMAGE_TYPE_LIST = {'jpg', 'bmp', 'png', 'jpeg', 'rgb', 'tif'}

@extend_schema(description='test_stream_http', request=None, responses=None)
@api_view(['GET', 'POST'])
@permission_classes((IsAuthenticated,))
def test_stream_http(request):
    def generate_data():
        for i in range(10):
            time.sleep(1)
            data = json.dumps({'i': i, 'msg': 'haha'})
            yield 'event: message\ndata: {} \n\n'.format(data)

    response = StreamingHttpResponse(generate_data(), content_type='text/event-stream')
    return response


@require_http_methods(['POST'])
def upload_file(request):
    if not request.user or not request.user.is_authenticated:
        return HttpResponseBadRequest('need authenticated')
    _type = request.GET.get('type')
    file = request.FILES.get('file')
    if not file:
        return HttpResponseBadRequest('Must have files attached!')

    tmp_filepath = os.path.join(settings.FILE_UPLOAD_DIR, file.name)
    res = default_storage.save(tmp_filepath, file)

    if _type == 'avatar':
        return JsonResponse({'avatar': res})

    uuid = request.POST.get('assistant')
    assistant = None
    if uuid:
        assistant = Assistant.objects.filter(uuid=uuid).first()
        if not assistant:
            return HttpResponseBadRequest('assistant {} not found'.format(uuid))

    filepath = os.path.join(settings.MEDIA_ROOT, res)

    if imghdr.what(filepath) in IMAGE_TYPE_LIST:
        file_type = 'image'
        purpose = 'vision'
        # file_id = 'file-iuoVbD2JpXXbcP0lgqKlt0ca',
    else:
        purpose = 'assistants'
        file_type = 'attachments'
        # file_id = 'file-kBBV2DYpak4YUbdPZ1qnv02Q'

    file_id = None
    if assistant and assistant.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
        print('upload file to openai ...')
        file_object = openai_api.upload_file(filepath, purpose)
        file_id = file_object.id

        if os.path.exists(filepath):
            os.remove(filepath)

    return JsonResponse({
        'file_id': file_id,
        'file_url': res,
        'file_type': file_type
    })


@require_http_methods(['GET'])
def file_content(request, fileid):
    if not request.user or not request.user.is_authenticated:
        return HttpResponseBadRequest('need authenticated')
    data = openai_api.client.files.content(file_id=fileid)
    resp = data.response
    response = HttpResponse(data.content)
    response['Content-Type'] = resp.headers['Content-Type']
    response['Content-Disposition'] = resp.headers['Content-Disposition']
    return response


class AssistantViewSet(viewsets.ModelViewSet):
    queryset = Assistant.objects.all()
    serializer_class = AssistantSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['name', ]
    filterset_fields = ['name', 'assistant_type', 'assistant_id', 'model', 'assistant_status', 'assistant_level',
                        'uuid']
    permission_classes = (IsAuthenticated,)
    ordering_fields = ('order_w', 'id')

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        if user.is_superuser:
            return queryset

        page_from = self.request.query_params.get('page_from')
        if page_from == 'store':
            return queryset

        extension = user.extension
        now_time = now()

        if now_time <= extension.expires_time:
            a_queyset = AssistantUser.objects.filter(user=self.request.user)
            aids = [i.assistant_id for i in a_queyset]
            return queryset.filter(Q(id__in=aids) | Q(assistant_level=Assistant.ASSISTANT_LEVEL_FREE))

        # queryset = queryset.filter(assistant_level=Assistant.ASSISTANT_LEVEL_FREE)
        queryset = queryset.filter(id=-1)
        return queryset

    def __clear_avatar_file(self, instance):
        if instance.avatar:
            old_avater_path = os.path.join(settings.MEDIA_ROOT, instance.avatar.url)
            if os.path.exists(old_avater_path):
                os.remove(old_avater_path)

    def __get_avatar_url(self, request):
        avatar = request.data.get('avatar')
        if avatar:
            src = os.path.join(settings.MEDIA_ROOT, avatar)
            file = os.path.split(src)[1]
            avatar_url = os.path.join('avatar', file)
            dst = os.path.join(settings.MEDIA_ROOT, avatar_url)
            with open(src, 'rb') as fp:
                c = ContentFile(fp.read())
                avatar_url = default_storage.save(dst, c)

            if os.path.exists(src):
                os.remove(src)

            return avatar_url
        return None

    def create(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'success': False, 'errorMessage': 'no permission'})

        request.data['creator'] = {'id': request.user.id}

        mode = request.data.get('mode')
        if mode == Assistant.ASSISTANT_MODE_ASSISTANT:
            assistant = openai_api.create_assistant(
                request.data.get('name'),
                instructions=request.data.get('instructions'),
                model=request.data.get('model'),
                top_p=request.data.get('top_p'),
                temperature=request.data.get('temperature')
            )
            request.data['assistant_id'] = assistant.id

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        headers = self.get_success_headers(serializer.data)

        if 'avatar' in request.data.keys():
            avatar_url = self.__get_avatar_url(request)
            instance.avatar = avatar_url
            instance.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def retrieve(self, request, pk=None):
        queryset = Assistant.objects.all()
        assistant = get_object_or_404(queryset, pk=pk)

        if request.query_params.get('remote'):
            if assistant.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
                resp = openai_api.get_assistant(assistant.assistant_id)
                return Response(resp.to_dict())

        serializer = AssistantSerializer(assistant)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'success': False, 'errorMessage': 'no permission'})

        instance = self.get_object()
        msgs = """{} update assistant {}({}):\nname: {}\ninstructions: {}\n
        """.format(request.user.username, instance.id, instance.name,
                   request.data.get('name'), request.data.get('instructions'))

        logging.info(msgs)
        if 'avatar' in request.data.keys():
            avatar_url = self.__get_avatar_url(request)

            if avatar_url:
                self.__clear_avatar_file(instance)

            instance.avatar = avatar_url
            instance.save()
            request.data.pop('avatar')

        if instance.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
            model = request.data.get('model')
            if not model and request.data.get('llm'):
                llm = Llm.objects.filter(uuid=request.data.get('llm')).first()
                model = llm.value
            try:
                openai_api.update_assistant(instance.assistant_id,
                                            instructions=request.data.get('instructions'),
                                            model=model,
                                            top_p=request.data.get('top_p'),
                                            temperature=request.data.get('temperature')
                                            )
            except NotFoundError:
                pass

        return super(AssistantViewSet, self).update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
            return Response({'success': False, 'errorMessage': 'no permission'})
        if instance.assistant_id and instance.assistant_status == Assistant.ASSISTANT_STATUS_ONLINE and instance.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
            try:
                openai_api.delete_assistant(instance.assistant_id)
            except NotFoundError:
                pass
            chats = Chat.objects.filter(assistant=instance).all()
            for chat in chats:
                if not chat.thread_id:
                    continue
                try:
                    openai_api.delete_thread(chat.thread_id)
                except NotFoundError:
                    pass

        self.__clear_avatar_file(instance)

        instance.delete()

    @action(methods=['post', ], detail=False)
    def test(self, request, *args, **kwargs):
        res = openai_api.list_assistant()
        return Response({'message': res.to_dict(), 'success': True})

    @action(methods=['post'], detail=False)
    def sync(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'success': False, 'errorMessage': 'no permission'})
        assistant_id = request.data.get('assistant_id')
        if assistant_id:
            res = sync_one_assistant(assistant_id)
        else:
            res = sync_all_assistants()
        return Response({'success': True, 'assistants': res})

    @action(methods=['get'], detail=False)
    def list_assistants(self, request, *args, **kwargs):
        if request.query_params.get('locale'):
            return super().list(request, args, kwargs)

        limit = 100
        name = request.query_params.get('name')
        aid = request.query_params.get('id')
        model = request.query_params.get('model')
        page_size = int(request.query_params.get('page_size', 10))
        page = int(request.query_params.get('page', 1))

        resp = openai_api.list_assistant(limit=limit)

        data = resp.to_dict().get('data')
        if not data:
            return Response({'results': [], 'count': 0})

        def condition(x):
            if name and name.strip() not in x.get('name'):
                return False
            if aid and aid.strip() not in x.get('id'):
                return False
            if model and model.strip() not in x.get('model'):
                return False
            return True

        datas = [x for x in data if condition(x)]

        limit = (page - 1) * page
        results = datas[limit: limit + page_size]
        return Response({'results': results, 'count': len(datas)})

    @action(methods=['get'], detail=False)
    def list_messages(self, request, *args, **kwargs):
        chatid = request.query_params.get('chatid')
        after = request.query_params.get('after')
        chat = Chat.objects.filter(id=chatid).first()
        if not chat:
            return Response({'success': False, 'errorMessage': 'not found this chat'})

        if chat.assistant.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
            thread_id = chat.thread_id
            # thread_id = 'thread_YFgoOVZYOyRbR0YTBNasCibX'
            data = openai_api.list_messages(thread_id, after=after)
            return Response({'success': True, 'messages': data.to_dict()})

        new_data = []
        if chat.messages:
            data = json.loads(chat.messages)
            new_data = filter(lambda x: x.get('role') != 'system', data)
        return Response({'success': True, 'messages': new_data})

    @action(methods=['post'], detail=False)
    def start_chat(self, request, *args, **kwargs):
        assistant_id = request.data.get('assistant_id')
        thread_id = request.data.get('thread_id')
        message = request.data.get('message')
        content = request.data.get('content')
        attachments = request.data.get('attachments')

        assistant = Assistant.objects.filter(assistant_id=assistant_id).first()
        if not assistant:
            return Response({'success': False, 'errorMessage': 'Not found this assistant'})

        if assistant.assistant_status != assistant.ASSISTANT_STATUS_ONLINE:
            return Response({'success': False, 'errorMessage': '此助手已下线、暂时无法使用'})

        ret, msg = check_user_assistant(request.user, assistant)
        if not ret:
            return Response({'success': True, 'errorMessage': msg})

        ret, msg = check_free_user_usage(request.user, content, attachments)
        if not ret:
            return Response({'success': True, 'usageCheck': False, 'checkMessage': msg})

        new_flag = False
        if not thread_id:
            thread = openai_api.create_thread()
            thread_id = thread.id
            new_flag = True
            chat = Chat(thread_id=thread_id, user=request.user, assistant=assistant)
            chat.save()
        else:
            chat = Chat.objects.filter(thread_id=thread_id, assistant=assistant).first()
            if not chat:
                return Response({'success': False, 'errorMessage': 'not found this chat'})

        chat_msg = openai_api.start_chat(assistant.assistant_id, content, thread_id, attachments=attachments)

        if new_flag:
            name = openai_api.get_title(message, chat_msg.content[0].text.value)
            chat.name = name
            chat.save()

        check_and_cache_free_user_usage(request.user)

        chat_data = ChatSerializer(chat).data
        return Response({'message': chat_msg.to_dict(), 'success': True, 'usageCheck': True, 'chat': chat_data})

    def _start_chat_stream_with_assistant(self, request, assistant, content, message, chat, attachments, new_flag):
        run_stream = openai_api.start_chat_by_stream(assistant.assistant_id, content, chat.thread_id,
                                                     attachments=attachments)

        check_and_cache_free_user_usage(request.user)

        chat_data = ChatSerializer(chat).data

        assistant_message = None

        def generate_data():
            for chunk in run_stream:
                if chunk.event == 'thread.run.created':
                    data = json.dumps(
                        {'success': True, 'usageCheck': True, 'event': 'start', 'stream': chunk.to_dict()})
                    yield 'event: message\ndata: {} \n\n'.format(data)
                else:
                    if chunk.event == 'thread.message.completed':
                        assistant_message = chunk.data.content[0].text.value
                    if chunk.event == 'thread.run.completed':
                        if new_flag:
                            name = openai_api.get_title(message, assistant_message)
                            chat.name = name
                            chat.save()
                        data = json.dumps(
                            {'success': True, 'event': 'completed', 'chat': chat_data, 'stream': chunk.to_dict()})
                        yield 'event: message\ndata: {} \n\n'.format(data)
                    else:
                        data = json.dumps({'success': True, 'stream': chunk.to_dict(), 'event': 'in_progress'})
                        yield 'event: message\ndata: {} \n\n'.format(data)

        response = StreamingHttpResponse(generate_data(), content_type='text/event-stream')
        return response

    def _start_chat_stream_with_chatapi(self, request, chat_assistant, assistant, content, message, chat, attachments, new_flag, chat_options,is_users_speak):

        # run_time_object = get_runtime(assistant.service_provider)
        run_time_object = get_runtime(assistant)
        chat_run = run_time_object(request, chat, assistant, content=content, message=message, new_flag=new_flag, chat_options=chat_options,is_users_speak=is_users_speak)
        send_messages = chat_run.pre_chat_completions()

        check_and_cache_free_user_usage(request.user)

        run_stream = chat_run.chat_completions(send_messages)

        def generate_data(streams):
            for chunk in streams:
                data = chat_run.do_chunk(chunk)
                if data:
                    yield 'event: message\ndata: {} \n\n'.format(data)

        response = StreamingHttpResponse(generate_data(run_stream), content_type='text/event-stream')
        return response

    def _check_assistant(self, user, assistant_uuid, content, attachments):
        assistant_queryset = Assistant.objects.filter(uuid=assistant_uuid)
        if assistant_queryset.count() > 1:
            return False, {'success': False, 'errorMessage': 'assistant_uuid 不唯一，请联系管理员'}

        assistant = assistant_queryset.first()
        if not assistant:
            return False, {'success': False, 'errorMessage': 'Not found this assistant'}

        if assistant.assistant_status != assistant.ASSISTANT_STATUS_ONLINE:
            return False, {'success': False, 'errorMessage': '此助手已下线、暂时无法使用'}

        ret, msg = check_user_assistant(user, assistant)
        if not ret:
            if msg == '账号已过期':
                return False, {'success': True, 'usageCheck': False, 'errorMessage': msg, 'checkMessage': '您的账号已过期' }
            return False, {'success': False, 'errorMessage': msg}

        ret, msg = check_free_user_usage(user, content, attachments)
        if not ret:
            return False, {'success': True, 'usageCheck': False, 'checkMessage': msg}
        return True, assistant


    @action(methods=['post'], detail=False)
    def start_chat_stream(self, request, *args, **kwargs):
        assistant_uuid = request.data.get('assistant_uuid')
        chat_assistant_uuid = request.data.get('chat_assistant_uuid')
        chat_uuid = request.data.get('chatid')
        message = request.data.get('message')
        content = request.data.get('content')
        attachments = request.data.get('attachments')
        chat_options = request.data.get('chat_options')

        def generate_data_error(resp_data):
            data = json.dumps(resp_data)
            yield 'event: message\ndata: {} \n\n'.format(data)

        def error_response(resp_data):
            return StreamingHttpResponse(generate_data_error(resp_data), content_type='text/event-stream')

        if not assistant_uuid:
            return error_response({'success': False, 'errorMessage': 'need assistant_uuid'})

        ret, res = self._check_assistant(request.user, assistant_uuid, content, attachments)
        if not ret:
            return error_response(res)

        assistant = res

        ret, res = self._check_assistant(request.user, chat_assistant_uuid, content, attachments)
        if not ret:
            return error_response(res)

        chat_assistant = res

        new_flag = False

        if chat_uuid:
            chat = Chat.objects.filter(uuid=chat_uuid).first()
            if not chat:
                return error_response({'success': False, 'errorMessage': 'not found this chat'})
        else:
            new_flag = True
            chat = Chat(user=request.user, assistant=chat_assistant)
            if assistant.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
                thread = openai_api.create_thread()
                chat.thread_id = thread.id
            chat.save()

            # chat member
            chat_member = AssistantChat(assistant=chat_assistant, chat=chat)
            chat_member.save()

            # assistant api 助手
        if assistant.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
            return self._start_chat_stream_with_assistant(request,  assistant, content, message, chat, attachments, new_flag)
        
        # chat api 模式助手
        return self._start_chat_stream_with_chatapi(request, chat_assistant, assistant, content, message, chat, attachments, new_flag, chat_options,False)

class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['thread_id', 'assistant_id', 'uuid', 'is_group']
    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            if self.request.query_params.get('all'):
                return queryset
        return queryset.filter(user=self.request.user)

    def _delete_thread(self, chat):
        if chat.assistant.mode == Assistant.ASSISTANT_MODE_ASSISTANT:
            return
        if not chat.thread_id:
            return
        try:
            openai_api.delete_thread(chat.thread_id)
        except NotFoundError:
            pass

    @action(methods=['get'], detail=False)
    def member(self, request, *args, **kwargs):
        chat_id = self.request.query_params.get('chat_id')
        chat = Chat.objects.filter(id=chat_id).first()
        if not chat:
            return Response({'success': False, 'message': ' chat存在'})

        #assistant = chat.assistant
        assistants = AssistantChat.objects.filter(chat=chat).all()

        assistant_ids = [i.assistant_id for i in assistants]
        # if assistant.id not in assistant_ids:
        #     assistant_ids.append(assistant.id)

        assistants = Assistant.objects.filter(id__in=assistant_ids)

        result = []
        for index,a in enumerate(assistants):
            a_data = SimpleAssistantSerializer(a).data
            if index == 0:
                a_data['helper_sequence']=chat.helper_sequence
            result.append(a_data)

        return Response({'success': True, 'results': result})

    @action(methods=['patch'], detail=False)
    def patch_member(self, request, *args, **kwargs):
        assistant_uuids = request.data.get('assistants')
        helperSequence = request.data.get('helper_sequence')
        chatid = request.data.get('chat')
        name = request.data.get('name')
        assistantid = request.data.get('assistant')
        is_group = request.data.get('is_group')
        if chatid:
            chat = Chat.objects.filter(uuid=chatid).first()
            if not chat:
                return Response({'success': False, 'message': 'chat 不存在'})
            chat.helper_sequence=helperSequence
            chat.save()
        else:
            if not name or not assistantid:
                return Response({'success': False, 'message': 'name 和 assistant 必填'})
            assistant = Assistant.objects.filter(uuid=assistantid).first()
            if not assistant:
                return Response({'success': False, 'message': ' assistant不存在'})

            chat = Chat(name=name, assistant=assistant, user=request.user, is_group=is_group,helper_sequence=helperSequence)
            chat.save() 


        ids = []
        for assistant_uuid in assistant_uuids:
            assistant = Assistant.objects.filter(uuid=assistant_uuid).first()
            if not assistant:
                continue

            ids.append(assistant.id)
            assistant_chat = AssistantChat.objects.filter(chat=chat, assistant=assistant).first()
            if not assistant_chat:
                assistant_chat = AssistantChat(assistant=assistant, chat=chat)
                assistant_chat.save()

        assistant_chats = AssistantChat.objects.filter(chat=chat).all()
        for assistant_chat in assistant_chats:
            if assistant_chat.assistant.id not in ids:
                assistant_chat.delete()

        chat_data = ChatSerializer(chat).data
        return Response({'success': True, 'chat': chat_data})

    def perform_destroy(self, instance):
        self._delete_thread(instance)
        instance.delete()

    @action(methods=['delete'], detail=False)
    def delete_chat(self, request, *args, **kwargs):
        user = request.user
        chats = Chat.objects.filter(user=user).all()
        for chat in chats:
            self._delete_thread(chat)
            chat.delete()
        return Response({'success': True})


    @action(methods=['delete'], detail=False)
    def batch_delete_chat(self, request, *args, **kwargs):
        chatids = request.data.get('chatids')
        chats = Chat.objects.filter(uuid__in=chatids).all()
        for chat in chats:
            self._delete_thread(chat)
            chat.delete()
        return Response({'success': True})


class AssistantUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AssistantUser.objects.all()
    serializer_class = AssistantUserSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['assistant_id', 'user_id']
    permission_classes = (IsAuthenticated,)

    @action(methods=['post'], detail=False)
    def update_user(self, request, *args, **kwargs):
        assistant_id = request.data.get('assistant_id')
        userids = request.data.get('userids')
        if not assistant_id or not userids:
            return Response({'success': False})

        assistant = Assistant.objects.filter(id=assistant_id).first()
        if not assistant:
            return Response({'success': False})

        ids = []
        for userid in userids:
            user = User.objects.filter(id=userid).first()
            if not user:
                continue
            ids.append(user.id)
            assistant_user = AssistantUser.objects.filter(assistant=assistant, user=user).first()
            if not assistant_user:
                assistant_user = AssistantUser(assistant=assistant, user=user)
                assistant_user.save()

        assistant_users = AssistantUser.objects.filter(assistant=assistant).all()
        for assistant_user in assistant_users:
            if assistant_user.user.id not in ids:
                assistant_user.delete()

        return Response({'success': True})


class AssistantChatViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AssistantChat.objects.all()
    serializer_class = AssistantChatSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['assistant_id', 'chat_id']
    permission_classes = (IsAuthenticated,)




class UsageBillingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UsageBilling.objects.all()
    serializer_class = UsageBillingSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['uuid', 'llm_name', 'user__username']
    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            if self.request.query_params.get('all'):
                return queryset
        return queryset.filter(user=self.request.user)


    @action(methods=['get'], detail=False)
    def chart_data(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'success': False, 'errorMessage': 'no permission'})

        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')

        queryset = UsageBilling.objects.filter(gmt_create__lte=end_time, gmt_create__gte=start_time).all()

        print(queryset)
        return Response({'success': True, 'data': []})


def start_chat_stream_with_chatapi(request, chat_assistant, assistant, content, message, chat, attachments,
                                   new_flag, chat_options,is_users_speak):
    run_time_object = get_runtime(assistant)
    chat_run = run_time_object(request, chat, assistant, content=content, message=message, new_flag=new_flag,chat_options=chat_options,is_users_speak=is_users_speak)
    # chat_run.soucre_assistant = source_assistant
    send_messages = chat_run.pre_chat_completions()
    check_and_cache_free_user_usage(request.user)

    run_stream = chat_run.chat_completions(send_messages)
    all_data = []
    for chunk in run_stream:
        data = chat_run.do_chunk(chunk)
        if data:
            all_data.append(data)

    response_data = {
        'success': True,
        'event': 'completed',
        'chat': ChatSerializer(chat).data,
        'stream': all_data
    }

    return JsonResponse(response_data)


def check_assistant(user, assistant_uuid, content, attachments):
    assistant_queryset = Assistant.objects.filter(uuid=assistant_uuid)
    if assistant_queryset.count() > 1:
        return False, {'success': False, 'errorMessage': 'assistant_uuid 不唯一，请联系管理员'}

    assistant = assistant_queryset.first()
    if not assistant:
        return False, {'success': False, 'errorMessage': 'Not found this assistant'}

    if assistant.assistant_status != assistant.ASSISTANT_STATUS_ONLINE:
        return False, {'success': False, 'errorMessage': '此助手已下线、暂时无法使用'}

    ret, msg = check_user_assistant(user, assistant)
    if not ret:
        return False, {'success': False, 'errorMessage': msg}

    ret, msg = check_free_user_usage(user, content, attachments)
    if not ret:
        return False, {'success': True, 'usageCheck': False, 'checkMessage': msg}
    return True, assistant


def check_assistant_filter(user, content, attachments,order):
    assistant_queryset = Assistant.objects.filter(auto_chat_order=order)
    if assistant_queryset.count() > 1:
        return False, {'success': False, 'errorMessage': 'assistant_uuid 不唯一，请联系管理员'}

    assistant = assistant_queryset.first()
    if not assistant:
        return False, {'success': False, 'errorMessage': 'Not found this assistant'}

    if assistant.assistant_status != assistant.ASSISTANT_STATUS_ONLINE:
        return False, {'success': False, 'errorMessage': '此助手已下线、暂时无法使用'}

    ret, msg = check_user_assistant(user, assistant)
    if not ret:
        return False, {'success': False, 'errorMessage': msg}

    ret, msg = check_free_user_usage(user, content, attachments)
    if not ret:
        return False, {'success': True, 'usageCheck': False, 'checkMessage': msg}
    return True, assistant
