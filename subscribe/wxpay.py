import os
import logging

from wechatpayv3 import WeChatPay, WeChatPayType
from django.conf import settings


# 商户证书私钥，此文件不要放置在下面设置的CERT_DIR目录里。
PRIVATE_KEY = None

# 微信支付平台证书缓存目录，初始调试的时候可以设为None，首次使用确保此目录为空目录。
CERT_DIR = os.path.join(settings.BASE_DIR, 'data/wxpay/.cert')

# 接入模式：False=直连商户模式，True=服务商模式。
PARTNER_MODE = False

# 代理设置，None或者{"https": "http://10.10.1.10:1080"}，详细格式参见[https://requests.readthedocs.io/en/latest/user/advanced/#proxies](https://requests.readthedocs.io/en/latest/user/advanced/#proxies)
PROXY = None

# 请求超时时间配置
TIMEOUT = (10, 30) # 建立连接最大超时时间是10s，读取响应的最大超时时间是30s

 
def get_wxpay():
    with open(settings.WEIXIN_PAY_PRIVATE_KEY_DIR) as f:
        PRIVATE_KEY = f.read()

    return WeChatPay(
        wechatpay_type=WeChatPayType.NATIVE,
        mchid=settings.WEIXIN_PAY_MCHID,
        private_key=PRIVATE_KEY,
        cert_serial_no=settings.WEIXIN_PAY_CERT_SERIAL_NO,
        apiv3_key=settings.WEIXIN_PAY_APIV3_KEY,
        appid=settings.WEIXIN_PAY_APPID,
        notify_url=settings.WEIXIN_PAY_NOTIFY_URL,
        cert_dir=CERT_DIR,
        logger=logging,
        partner_mode=PARTNER_MODE,
        proxy=PROXY,
        timeout=TIMEOUT
    )
