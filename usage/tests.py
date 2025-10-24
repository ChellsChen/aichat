from django.test import TestCase

# Create your tests here.
from usage.utils import sync_usage_billing_date, sync_billing_date


class UsageTestCase(TestCase):
    def test_sync(self):
        sync_usage_billing_date('2025-02-11')


    def test_billing_date(self):
    	sync_billing_date()



