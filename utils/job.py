import ast
import base64
import json
import pickle
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.date import DateTrigger
from django.contrib.auth.models import User
from rest_framework.response import Response

import logging

from django.http import StreamingHttpResponse

from assistant import views
from assistant.models import Chat, Assistant, AssistantChat
from component.models import ScheduledTasksLog
from oceanengine import functions
from oceanengine.oceanengine_api import oceanengine_api


from utils.redis import RedisUtil


class SchedulerManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SchedulerManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.init_scheduler()
        return cls._instance

    def init_scheduler(self):
        self.jobstores = {
            'default': MemoryJobStore()
        }
        self.executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }
        self.job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': None  # 不限制任务的可执行时间

        }
        self.scheduler = BackgroundScheduler(jobstores=self.jobstores, executors=self.executors,
                                             job_defaults=self.job_defaults)

    def start(self):
        self.scheduler.start()
    def is_scheduler_running(self):
        """
        检查定时任务是否已启动
        :return: 如果定时任务正在运行，返回True；否则返回False
        """
        return self.scheduler.running
    #关闭
    def shutdown(self, wait=True):
        """关闭调度器"""
        try:
            # 获取所有任务
            jobs = self.get_jobs()
            # 清除所有任务状态
            for job in jobs:
                TaskLogic.clear_task_status(job.id)
            # 关闭调度器
            self.scheduler.shutdown(wait)
        except Exception as e:
            logging.error(f"关闭调度器失败: {str(e)}")

    def add_job(self, func, trigger, **kwargs):
        return self.scheduler.add_job(func, trigger, **kwargs)

    def remove_job(self, job_id):
        """移除任务"""
        try:
            TaskLogic.set_task_status(job_id, 'stopped')
            time.sleep(1)
            TaskLogic.clear_task_status(job_id)
            try:
                self.scheduler.remove_job(job_id)
            except Exception as e:
                logging.warning(f"移除调度任务失败(可能任务不存在): {str(e)}")
            return True
        except Exception as e:
            logging.error(f"移除任务失败: {str(e)}")
            return False

    def get_jobs(self):
        return self.scheduler.get_jobs()

    def pause_job(self, job_id):
        """暂停指定的任务"""
        try:
            current_status = TaskLogic.get_task_status(job_id)
            if current_status != 'running':
                return False

            TaskLogic.set_task_status(job_id, 'paused')
            try:
                self.scheduler.pause_job(job_id)
            except Exception as e:
                logging.warning(f"APScheduler暂停任务失败(可能任务正在执行): {str(e)}")
            return True
        except Exception as e:
            logging.error(f"暂停任务失败: {str(e)}")
            return False

    def resume_job(self, job_id):
        """恢复指定的任务"""
        try:
            current_status = TaskLogic.get_task_status(job_id)
            if current_status != 'paused':
                return False

            text, request = TaskLogic.get_task_params(job_id)
            if not request:
                logging.error(f"未找到任务参数: {job_id}")

            TaskLogic.set_task_status(job_id, 'running')
            trigger = DateTrigger(run_date=datetime.now())
            self.add_job(TaskLogic.groupChat, 'date',
                        run_date=trigger.run_date,
                        args=(job_id, text, request),
                        id=job_id)
            return True
        except Exception as e:
            logging.error(f"恢复任务失败: {str(e)}")
            return False

    # 获取指定的任务对象
    def get_job(self, job_id):
        return self.scheduler.get_job(job_id)

    # 获取指定任务的状态
    def get_job_state(self, job_id):
        """获取任务状态"""
        job = self.scheduler.get_job(job_id)
        if not job:
            return None
        return job.next_run_time is None  # True表示暂停状态

    # 移除所有任务
    def remove_all_jobs(self):
        self.scheduler.remove_all_jobs()


class TaskLogic:
    # 添加任务状态控制
    _task_status = {}  # 用于存储任务状态
    _redis = RedisUtil()  # 直接使用 RedisUtil 实例

    @staticmethod
    def set_task_status(task_id, status, text=None, request=None):
        """设置任务状态和参数"""
        try:
            TaskLogic._redis.set(f"task_status:{task_id}", status, timeout=86400)

            if status == 'paused':
                current_index = TaskLogic._redis.get(f"task_index:{task_id}")
                if current_index is not None:
                    TaskLogic._redis.set(f"paused_index:{task_id}", current_index, timeout=86400)

            # 直接存储 text 和 request
            if text is not None:
                TaskLogic._redis.set(f"task_text:{task_id}", text, timeout=86400)

            if request is not None:
                # 只保存必要的 request 属性
                request_data = {
                    'user': request.user.id if hasattr(request.user, 'id') else None,
                    'method': request.method,
                    'GET': dict(request.GET),
                    'POST': dict(request.POST),
                    'META': {k: str(v) for k, v in request.META.items()},
                }
                TaskLogic._redis.set(f"task_request:{task_id}", json.dumps(request_data), timeout=86400)
        except Exception as e:
            logging.error(f"设置任务状态和参数失败: {str(e)}")


    @staticmethod
    def get_task_params(task_id):
        """获取任务参数"""
        try:
            text = TaskLogic._redis.get(f"task_text:{task_id}")
            if isinstance(text, bytes):
                text = text.decode('utf-8')

            request_data = TaskLogic._redis.get(f"task_request:{task_id}")
            if request_data:
                if isinstance(request_data, bytes):
                    request_data = request_data.decode('utf-8')
                request_dict = json.loads(request_data)

                # 重建 request 对象
                from django.http import HttpRequest
                from django.contrib.auth.models import User
                request = HttpRequest()
                request.method = request_dict.get('method', 'GET')
                request.GET = request_dict.get('GET', {})
                request.POST = request_dict.get('POST', {})
                request.META = request_dict.get('META', {})
                if request_dict.get('user'):
                    request.user = User.objects.get(id=request_dict['user'])
            else:
                request = None

            return text, request
        except Exception as e:
            logging.error(f"获取任务参数失败: {str(e)}")
            return None, None

    @staticmethod
    def get_task_status(task_id):
        """获取任务状态"""
        try:
            status = TaskLogic._redis.get(f"task_status:{task_id}")
            if status is None:
                return 'running'
            if isinstance(status, bytes):
                return status.decode('utf-8')
            return status
        except Exception as e:
            logging.error(f"获取任务状态失败: {str(e)}")
            return 'running'

    @staticmethod
    def set_current_index(task_id, index):
        """保存当前执行的索引"""
        current_status = TaskLogic.get_task_status(task_id)
        # 只有在暂停状态下才记录索引
        if current_status == 'paused':
            TaskLogic._redis.set(f"task_index:{task_id}", str(index), timeout=86400)

    @staticmethod
    def get_paused_index(task_id):
        """获取暂停时的索引"""
        try:
            index = TaskLogic._redis.get(f"paused_index:{task_id}")
            if index is None:
                return 0
            return int(index.decode('utf-8') if isinstance(index, bytes) else index)
        except Exception:
            return 0

    @staticmethod
    def clear_task_status(task_id):
        """清除任务相关的所有状态"""
        try:
            TaskLogic._redis.delete(f"task_status:{task_id}")
            TaskLogic._redis.delete(f"task_index:{task_id}")
            TaskLogic._redis.delete(f"paused_index:{task_id}")
            TaskLogic._redis.delete(f"task_text:{task_id}")
            TaskLogic._redis.delete(f"task_request:{task_id}")
        except Exception as e:
            logging.error(f"清除任务状态失败: {str(e)}")

    @staticmethod
    def groupChat(chat_uuid, text, request):
        print("定时任务开始执行了")
        try:
            # 如果是新任务，保存参数
            if not TaskLogic._redis.exists(f"task_request:{chat_uuid}"):
                TaskLogic.set_task_status(chat_uuid, 'running', text, request)

            chat = Chat.objects.filter(uuid=chat_uuid).first()
            if not chat or not chat.helper_sequence:
                print("未找到聊天记录或助手序列为空")
                TaskLogic.clear_task_status(chat_uuid)
                return

            try:
                jsonSequence = sorted(ast.literal_eval(chat.helper_sequence), key=lambda x: x['value'])
            except (ValueError, SyntaxError) as e:
                logging.error(f"解析helper_sequence失败: {str(e)}")
                TaskLogic.clear_task_status(chat_uuid)
                return

            contents = ''
            num = len(jsonSequence)

            # 确定开始索引
            start_index = TaskLogic.get_paused_index(chat_uuid)

            for index in range(start_index, num):
                # 检查任务状态
                current_status = TaskLogic.get_task_status(chat_uuid)
                if current_status == 'paused':
                    TaskLogic.set_current_index(chat_uuid, index)
                    print(f"任务已暂停，当前索引: {index}")
                    return
                elif current_status == 'stopped':
                    print("任务已停止")
                    TaskLogic.clear_task_status(chat_uuid)
                    return

                i = jsonSequence[index]
                id = i.get('key')
                if not id:
                    continue

                contents = TaskLogic.loop(assistant_id=id, text=text, contents=contents,
                                          chat=chat, request=request, iding=id)

            print("定时任务执行完成了")
            TaskLogic.clear_task_status(chat_uuid)

        except Exception as e:
            logging.error(f"执行任务出错: {str(e)}")
            TaskLogic.set_task_status(chat_uuid, 'error')

    @staticmethod
    def loop(assistant_id, text, contents, chat, request, iding):
        attachments = ''
        message = ''
        new_flag = False
        if contents != '':
            content = [
                {
                    "text": contents,
                    "type": "text"
                }
            ]
        else:
            content = [
                {
                    "text": text,
                    "type": "text"
                }
            ]
        ret, res = views.check_assistant(request.user, assistant_id, content, attachments)
        ret, resing = views.check_assistant(request.user, iding, content, attachments)
        if contents != '':
            repose = views.start_chat_stream_with_chatapi(request, res, res, content, message, chat,
                                                          attachments, new_flag, resing,True)
        else:
            chat_options = {}
            repose = views.start_chat_stream_with_chatapi(request, res, res, content, message, chat,
                                                          attachments, new_flag, chat_options,False)

        # 获取 content 属性并解码为字符串
        # 历史记录 取的最后一条
        num = len(json.loads(repose.content.decode('utf-8')).get('chat', {}).get('messages', ''))
        contents = \
        json.loads(repose.content.decode('utf-8')).get('chat', {}).get('messages', '')[num - 1].get('content')[0].get(
            'text')
        return contents

    @staticmethod
    def tasks(advertiser_id, new_flag, request,ad_id,chat_uuid):
        ret, refresh_token = functions._get_access_token_by_request(request)

        filtering = {
            'marketing_goal': 'LIVE_PROM_GOODS',
            'ids': [ad_id]
        }
        def custom_serializer(obj):
            if hasattr(obj, 'to_json'):
                return obj.to_json()  # 对象有 to_json 方法时使用该方法
            return str(obj)  # 默认转为字符串

        # 使用自定义序列化方法进行序列化
        filtering_str = json.dumps(filtering, default=custom_serializer)
        res = oceanengine_api.get_ad_list(refresh_token, advertiser_id, filtering=filtering_str, page_size=100)
        if res.get('code')!=0:
            return Response({'success': False, 'errorMessage': '查询第三方接口错误！'})
        resing = res.get('data', {}).get('list')

        # 预算 roi 出价
        name = resing[0].get('name')
        ad_id = resing[0].get('ad_id')
        budget = resing[0].get('delivery_setting').get('budget')
        roi_goal = resing[0].get('delivery_setting').get('roi_goal')
        cpa_bid = resing[0].get('delivery_setting').get('cpa_bid')
        if not cpa_bid:
            cpa_bid = 0

        if not roi_goal:
            roi_goal = 0

        if not budget:
            budget = 0

        assistant_uuid = request.data.get('assistant_uuid')
        chat_assistant_uuid = request.data.get('chat_assistant_uuid')
        chat_uuid = request.data.get('chatid')
        message = request.data.get('message')
        content = request.data.get('content')
        attachments = request.data.get('attachments')

        def generate_data_error(resp_data):
            data = json.dumps(resp_data)
            yield 'event: message\ndata: {} \n\n'.format(data)

        def error_response(resp_data):
            return StreamingHttpResponse(generate_data_error(resp_data), content_type='text/event-stream')

        if chat_uuid:
            chat = Chat.objects.filter(uuid=chat_uuid).first()
        ret, res = views.check_assistant(request.user, assistant_uuid, content, attachments)
        if not ret:
            return error_response(res)
        assistant = res
        ret, res = views.check_assistant(request.user,chat_assistant_uuid,content, attachments)
        if not ret:
            return error_response(res)
        chat_assistant = res
        order='one'
        ret, source_assistant = views.check_assistant_filter(request.user,content, attachments,order)
        order='two'
        ret, assistanting = views.check_assistant_filter(request.user,content, attachments,order)

        chat.assistant = chat_assistant
        content = [
            {
                "text": f'预算:{budget},roi:{roi_goal},出价:{cpa_bid}',
                "type": "text"
            }
        ]
        repose = views.start_chat_stream_with_chatapi(request, assistanting, assistanting, content, message, chat,
                                                      attachments, new_flag,source_assistant)
        # 获取 content 属性并解码为字符串
        # 历史记录 取的最后一条
        num = len(json.loads(repose.content.decode('utf-8')).get('chat', {}).get('messages', ''))
        contents =json.loads(repose.content.decode('utf-8')).get('chat', {}).get('messages', '')[num-1].get('content')[0].get('text')

        order='three'
        ret, assistant_queryset = views.check_assistant_filter(request.user,content, attachments,order)

        texting=f'计划名称:{name},计划id:{ad_id}'+contents
        contenting = [
            {
                "text": texting,
                "type": "text"
            }
        ]
        views.start_chat_stream_with_chatapi(request, assistant_queryset, assistant_queryset, contenting, message, chat,
                                                      attachments, new_flag,assistanting)

        if chat_uuid:
            chat = Chat.objects.filter(uuid=chat_uuid).first()
        ret, res = views.check_assistant(request.user, assistant_uuid, content, attachments)
        if not ret:
            return error_response(res)
        assistant = res
        chat.assistant = assistant

        messages = json.loads(chat.messages)

        filtered_data = [item for item in messages if item.get("role") != "user"]

        # 将过滤后的数据转换回 JSON 格式
        filtered_json = json.dumps(filtered_data)
        chat.messages = filtered_json
        chat.save()

        #保存到定时任务日志表
        result=ScheduledTasksLog.objects.filter(task_id=chat_uuid,is_delete=0).first()
        if result:
            num=result.execution_frequency
            num=num+1
            result.execution_frequency=num
            ScheduledTasksLog.save(result)
        else:
            def custom_serializer(obj):
                if hasattr(obj, 'to_json'):
                    return obj.to_json()  # 对象有 to_json 方法时使用该方法
                return str(obj)  # 默认转为字符串
            user = json.dumps(request.user, default=custom_serializer)
            request_data= json.loads(json.dumps({'advertiser_id': advertiser_id, 'new_flag': new_flag, 'request': user, 'ad_id': ad_id}))

            authUser=User.objects.filter(id=request.user.id).first()
            assistantChat=AssistantChat.objects.filter(uuid=chat_uuid).first()

            ScheduledTasksLog.save(request_data=request_data, task_name='自动对话托管化',task_id=chat_uuid, user_id=request.user.id,user_name=authUser.username,
                                   task_status=ScheduledTasksLog.TASK_STATUS_IN_EXECUTION, execution_frequency=1,group_chat_name=assistantChat.name)

    @staticmethod
    def test(advertiser_id, new_flag, request, ad_id):
        print('test')
