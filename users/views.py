import logging
import hashlib
import random
import string

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.utils.timezone import now
from django.conf import settings

from rest_framework import filters
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from users.serializers import UserSerializer, UserLoginSerializer, UserLoginRequestSerializer
from aichat.permissions import ModelCRUDPermission
from aichat.pagination import StandardResultsPagination
from users.models import UserExtension
from utils.aliyun_api import send_sms_code
from assistant.models import Assistant, AssistantUser


# Create your views here.

logger = logging.getLogger(__name__)



@extend_schema(description='sms_code', request=None, responses=None)
@api_view(['GET', ])
@permission_classes((AllowAny,))
def get_captcha(request):
    phone = request.query_params.get('phone')
    _type = request.query_params.get('type')
    if _type not in ['register', 'reset']:
        return JsonResponse({
            'success': False,
            'errorMessage':'参数错误'
        })
    if not phone:
        return JsonResponse({
            'success': False,
            'errorMessage':'请输入手机号'
        })

    if _type == 'reset':
        extension = UserExtension.objects.filter(phone=phone).first()
        if not extension:
            return JsonResponse({
                'success': False,
                'errorMessage':'手机号 {} 未注册，请先注册'.format(phone)
            })
    if _type == 'register':
        extension = UserExtension.objects.filter(phone=phone).first()
        if extension:
            return JsonResponse({
                'success': False,
                'errorMessage':'手机号 {} 已被注册'.format(phone)
            })

    ttl = cache.ttl(phone)
    timeout = 60 * 10
    waittime = 60 * 1
    max_timeout = timeout - waittime
    if ttl and ttl >= max_timeout:
        return JsonResponse({
            'success': False,
            'errorMessage':'请一分钟后再试'
        }) 

    code_number = ''.join(random.sample(string.digits, 6))
    cache.set(phone, code_number, timeout=timeout)
    send_sms_code(phone, code_number)
    return JsonResponse({
        'success': True,
        'code': '-'
    })


@extend_schema(description='login', 
    request=UserLoginRequestSerializer,
    responses={
            200: OpenApiResponse(response=UserLoginSerializer,
                                 description='Created. New resource in response'),
            401: OpenApiResponse(description='Bad request (something invalid)'),
        })
@api_view(['POST', ])
@permission_classes((AllowAny,))
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    if not username or not password:
    	return HttpResponse('need username or password')

    user = User.objects.filter(username=username).first()
    if not user:
        return HttpResponse('账号不存在', status=400) 

    user = authenticate(request, username=username, password=password)
    if user is None:
        return HttpResponse('密码错误', status=400)

    # if not user.is_superuser:
    #     if user.extension.expires_time <= now():
    #         return HttpResponse('账号已过期，请联系管理员', status=401) 

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    logger.info('user {} login'.format(username))
    return JsonResponse({
        'status': 'ok',
        'type': 'access',
        'currentAuthority': 'user'
    })


@extend_schema(description='logout', request=None, responses=None)
@api_view(['POST', ])
@permission_classes((AllowAny,))
def logout_view(request):
    username = request.user.username
    logout(request)
    logger.info('user {} logout'.format(username))
    return JsonResponse({
        'data': {},
        'success': True
    })


@extend_schema(description='register', request=None, responses=None)
@api_view(['POST', ])
@permission_classes((AllowAny,))
def register_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    password1 = request.data.get('password1')

    phone = request.data.get('phone')
    captcha = request.data.get('captcha')

    if not username or not password:
        return HttpResponse('need username or password')
    if password1 != password:
        return HttpResponse('两次密码输入不一致！')

    same_name_user = User.objects.filter(username=username).first()
    if same_name_user:
        return HttpResponse('账号 {} 已被注册'.format(username))

    if not phone:
        return HttpResponse('手机号不能为空')

    extension = UserExtension.objects.filter(phone=phone).first()
    if extension:
        return HttpResponse('手机号 {} 已被注册'.format(phone))

    code = cache.get(phone)
    if not captcha:
        return HttpResponse('短信验证码不能为空')
    if not code:
        return HttpResponse('短信验证码已过期，请重新获取短信验证码')
    if code != captcha:
        return HttpResponse('短信验证码错误，请输入正确的短信验证码')

    has_str_num = any([i.isupper() or i.islower() or i.isdigit() for i in password])
    if has_str_num and len(password) >= 6:
        user =  User.objects.create_user(username=username, password=password)
        user.extension.phone = phone
        user.save()

        for _id in settings.USER_FREE_USE_ASSISTANT_IDS:
            assistant = Assistant.objects.filter(id=_id).first()
            assistant_user = AssistantUser(assistant=assistant, user=user)
            assistant_user.save()

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        logger.info('user {} register and login'.format(username))
        return JsonResponse({
            'status': 'ok',
            'type': 'access',
            'currentAuthority': 'user'
        })
    return HttpResponse('密码不符合规则：至少包含一个数字、一个字母，长度至少为6位')



@extend_schema(description='reset_password', request=None, responses=None)
@api_view(['POST', ])
@permission_classes((AllowAny,))
def reset_password(request):
    username = request.data.get('username')
    phone = request.data.get('phone')
    password = request.data.get('password')
    password1 = request.data.get('password1')
    captcha = request.data.get('captcha')
    code = cache.get(phone)

    user = User.objects.filter(username=username).first()
    if not user:
        return HttpResponse('用户 {} 不存在，请先注册账号'.format(username))
    if not phone:
        return HttpResponse('手机号不能为空')
    extension = UserExtension.objects.filter(phone=phone).first()
    if not extension:
        return HttpResponse('手机号未注册，请先注册账号')
    if not user.extension:
        return HttpResponse('用户无手机信息，请联系管理员')
    if user.extension.phone != phone:
        return HttpResponse('用户手机号信息不正确')
    if password1 != password:
        return HttpResponse('两次密码输入不一致！')
    if not captcha:
        return HttpResponse('短信验证码不能为空')
    if not code:
        return HttpResponse('短信验证码已过期，请重新获取短信验证码')
    if code != captcha:
        return HttpResponse('短信验证码错误，请输入正确的短信验证码')

    has_str_num = any([i.isupper() or i.islower() or i.isdigit() for i in password])
    if has_str_num and len(password) >= 6:
        user.set_password(password)
        user.save()
        ret = JsonResponse({
            'status': 'ok',
        })
        #ret.delete_cookie(request.user.username)
        return ret

    return HttpResponse('密码不符合规则：至少包含一个数字一个字母，至少为6位')


@extend_schema(description='register', request=None, responses=None)
@api_view(['GET'])
@authentication_classes((SessionAuthentication,))
@permission_classes((AllowAny,))
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({
            'data': {
                'isLogin': False,
            },
            'errorCode': '401',
            'errorMessage': '请先登录！',
            'success': False,

        }, status=401)

    # if not request.user.is_superuser and request.user.extension.expires_time < now():
    #     return JsonResponse({
    #         'data': {
    #             'isLogin': False,
    #         },
    #         'errorCode': '401',
    #         'errorMessage': '账号已过期，请联系管理员',
    #         'success': False,

    #     }, status=401)

    username = request.user.first_name
    if not username:
        username = request.user.username

    admin_str = 'username={}&admin={}'.format(username, request.user.is_superuser)
    g_token = hashlib.new('md5', admin_str.encode('utf-8')).hexdigest()

    extension = request.user.extension
    
    return JsonResponse({
        'success': True,
        'data': {
            'name': username,
            'avatar': 'https://gw.alipayobjects.com/zos/antfincdn/XAosXuNZyF/BiazfanxmamNRoxxVxka.png',
            'userid': request.user.id,
            'phone': extension.phone,
            'expires_time': extension.expires_time,
            'date_joined': request.user.date_joined,
            'user_level': extension.user_level,
            'gtoken': g_token
            # 'permissions': request.user and list(request.user.get_all_permissions())
        }
    })


@extend_schema(description='get_user_info', request=None, responses=None)
@api_view(['GET'])
@authentication_classes((SessionAuthentication,))
@permission_classes((AllowAny,))
def get_user(request):
    username = request.query_params.get('username')
    user = User.objects.filter(username=username).first()
    if not user:
        return JsonResponse({'success': False, 'errorMessage': '账号 {} 不存在，请先注册'.format(username)})

    extension = user.extension
    if not extension:
        return JsonResponse({'success': False, 'errorMessage': '账号 {} 无手机信息，请联系管理员'.format(username)})
    return JsonResponse({
        'success': True,
        'data': {'phone': extension.phone, 'username': username}
    })


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-id')
    serializer_class = UserSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['username', ]
    filterset_fields = ['username', ]
    permission_classes = (ModelCRUDPermission, )


    @action(methods=['get'], detail=False)
    def simplelist(self,request, *args, **kwargs):
        res = User.objects.all()
        data = [{'value': i.id, 'label': i.username} for i in res]
        return Response(data)

    def update(self, request, *args, **kwargs):
        extension_data  = request.data.get('extension')
        if extension_data:
            extension = UserExtension.objects.filter(id=extension_data.get('id')).first()
            if extension:
                if extension_data.get('phone'):
                    extension.phone = extension_data.get('phone')
                if extension_data.get('user_level'):
                    extension.user_level = extension_data.get('user_level')
                if extension_data.get('expires_time'):
                    extension.expires_time = extension_data.get('expires_time')
                extension.save()


        assistants = request.data.get('assistants')
        userid = request.data.get('id')
        user = User.objects.filter(id=userid).first()
        if assistants and user:
            ids = []
            for assistant_id in assistants:
                assistant = Assistant.objects.filter(id=assistant_id).first()
                if not assistant:
                    continue

                ids.append(assistant.id)
                assistant_user = AssistantUser.objects.filter(assistant=assistant, user=user).first()
                if not assistant_user:
                    assistant_user = AssistantUser(assistant=assistant, user=user)
                    assistant_user.save()

            assistant_users = AssistantUser.objects.filter(user=user).all()
            for assistant_user in assistant_users:
                if assistant_user.assistant.id not in ids:
                    assistant_user.delete()

        if extension_data.get('user_level') == 'default':
            AssistantUser.objects.filter(user=user).delete()

        return super(UserViewSet, self).update(request, *args, **kwargs)





