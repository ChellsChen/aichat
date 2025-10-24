import logging
from django.contrib import admin
from subscribe.models import SubscribePlan, SubscribePlanTime, SubscribePlanHistory
from subscribe.utils import validate_wxpay_success, process_pay_success
# Register your models here.

@admin.register(SubscribePlan)
class SubscribePlanAdmin(admin.ModelAdmin):
    filter_horizontal = ('assistants', )
    list_display = ('name', 'price_per_month', 'description', 'remark')


@admin.register(SubscribePlanTime)
class SubscribePlanTimeAdmin(admin.ModelAdmin):
    list_display = ('name', 'timedelta_month', 'discount', 'price')


@admin.register(SubscribePlanHistory)
class SubscribePlanHistoryAdmin(admin.ModelAdmin):
    search_fields = ('name', 'trade_no')
    list_filter = ["status", ]
    list_display = ('name', 'price', 'user', 'status', 'trade_no', 'gmt_completed')


    def save_model(self, request, obj, form, change):
        old_obj = SubscribePlanHistory.objects.filter(id=obj.id).first()
        if obj.status == SubscribePlanHistory.STATUS_COMPLETED and old_obj.status == SubscribePlanHistory.STATUS_PENDING:
            ret, pay_data = validate_wxpay_success(obj.trade_no)
            if ret:
                logging.info('trade_no {} has pay success'.format(obj.trade_no))
                obj = process_pay_success(obj.trade_no, pay_data)
        super().save_model(request, obj, form, change)

