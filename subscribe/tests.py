from django.test import TestCase
from subscribe.wxpay import get_wxpay
from wechatpayv3 import WeChatPayType
from subscribe.tasks import clear_pending_timeout_history_task
from subscribe.utils import validate_wxpay_success, process_pay_success

# Create your tests here.

class PayTestCase(TestCase):
    def test_gen_code(self):
        wxpay = get_wxpay()

        name = 'test-pay'
        trade_no = '102410214401'
        price = 1
        code, message = wxpay.pay(
            description=name,
            out_trade_no=trade_no,
            amount={'total': price},
            pay_type=WeChatPayType.NATIVE
        )
        print(code)
        print(message)

    def test_wxpay_results(self):
        ret, success_time = validate_wxpay_success('10241108022156343')
        print(success_time)
        # if ret:
        #     process_pay_success('10241108022156343')



    def test_clear_pending_timeout_history_task(self):
        clear_pending_timeout_history_task()