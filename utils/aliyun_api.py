# -*- coding: utf-8 -*-
import json

from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient

from django.conf import settings


def send_sms_code(phone_numbers, code):
    template_param = json.dumps({'code': code})
    access_key_id = settings.ALIYUN_ACCESS_KEY_ID
    access_key_secret = settings.ALIYUN_ACCESS_KEY_SECRET
    endpoint = settings.ALIYUN_SMS_ENDPOINT

    sign_name = settings.ALIYUN_SMS_SIGN_NAME
    template_code = settings.ALIYUN_SMS_TEMPLATE_CODE

    config = open_api_models.Config(access_key_id=access_key_id,access_key_secret=access_key_secret)
    config.endpoint = endpoint
    client = Dysmsapi20170525Client(config)

    send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
        sign_name=sign_name,
        template_code=template_code,
        phone_numbers=phone_numbers,
        template_param=template_param
    )
    runtime = util_models.RuntimeOptions()
    try:
        # 复制代码运行请自行打印 API 的返回值
        client.send_sms_with_options(send_sms_request, runtime)
    except Exception as error:
        # 此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常。
        # 错误 message
        print(error.message)
        # 诊断地址
        print(error.data.get("Recommend"))
        UtilClient.assert_as_string(error.message)



if __name__ == '__main__':
    send_sms_code('15088750572', '542941')
