from functools import wraps
from django.http import HttpResponse

from partners.models import PartnerInfo
from oceanengine.utils import get_access_token

def check_api_key(func):
    """验证 ui token 装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        request = args[0]
        api_secret = request.META.get('HTTP_X_API_SECRET')
        partner_info = PartnerInfo.objects.filter(api_secret_key=api_secret).first()
        if not partner_info:
            return HttpResponse('unauthorized!')
        tokens = partner_info.tokens
        if not tokens:
            return HttpResponse('还未授权请稍后再试!')
        request.api_secret_key = api_secret

        ret, token = get_access_token(api_secret)
        if not ret:
            return HttpResponse(token)
        request.token = token
        return func(*args, **kwargs)
    return wrapper