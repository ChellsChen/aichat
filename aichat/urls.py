"""
URL configuration for qiwuai project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.views import static
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from rest_framework import routers
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from users import views
from assistant.views import AssistantViewSet, ChatViewSet, upload_file, file_content, AssistantUserViewSet, test_stream_http, AssistantChatViewSet
from assistant.views import AssistantViewSet, ChatViewSet, upload_file, file_content, AssistantUserViewSet, \
    test_stream_http, AssistantChatViewSet, UsageBillingViewSet
from subscribe.views import SubscribePlanViewSet, SubscribePlanTimeViewSet, SubscribePlanHistoryViewSet, wxpay_pay_action, gen_pay_code
from llm.views import LlmViewSet
from usage.views import UsageBillingViewSet

router = routers.DefaultRouter()

router.register(r'users', views.UserViewSet, basename='users')
router.register(r'assistant', AssistantViewSet, basename='assistant')
router.register(r'assistantuser', AssistantUserViewSet, basename='assistantuser')
router.register(r'assistantchat', AssistantChatViewSet, basename='assistantchat')
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'subscribe/plan', SubscribePlanViewSet, basename='subscribe_plan')
router.register(r'subscribe/plan_time', SubscribePlanTimeViewSet, basename='subscribe_plan_time')
router.register(r'subscribe/plan_history', SubscribePlanHistoryViewSet, basename='subscribe_plan_history')
router.register(r'llm/model', LlmViewSet, basename='llm_model')
router.register(r'usagebilling', UsageBillingViewSet, basename='usagebilling')


urlpatterns = [
    re_path(r'v1/', include(router.urls)),
    path('admin/', admin.site.urls),
    path('login/captcha/', views.get_captcha),
    path('login/account', views.login_view),
    path('register/account', views.register_view),
    path('login/outLogin', views.logout_view),
    path('login/resetpassword', views.reset_password),
    path('login/userphone', views.get_user),
    path('v1/gen/pay/code', gen_pay_code),
    path('v1/wxpay/action', wxpay_pay_action, name='wxpay_pay_action'),

    path('currentUser', views.current_user),
    # path('oauth/callback/', oauth_callback, name='oauth_callback'),
    path('upload/file/', upload_file, name='upload_file'),
    path('file/<fileid>/', file_content, name='file_content'),
    path('v1/test/stream/', test_stream_http, name='test_stream_http'),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),  # swagger接口文档
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),  # redoc接口文档
    re_path(r'^static/(?P<path>.*)$', static.serve, {'document_root': settings.STATIC_ROOT}, name='static'),
    re_path(r'^media/(?P<path>.*)$', static.serve, {'document_root': settings.MEDIA_ROOT}, name='media'),
    re_path(r'^uploadsfile/(?P<path>.*)$', static.serve, {'document_root': settings.FILE_UPLOAD_DIR}, name='uploadsfile'),
]

urlpatterns += staticfiles_urlpatterns()