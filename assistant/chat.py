import json
import os
import logging
import mimetypes

from django.conf import settings
from assistant.tools import call_function
from assistant.serializers import ChatSerializer
from assistant.models import UsageBilling
from llm.client import openai_api, anthropic_api, doubao_api, OpenAI_API, Anthropic_API, DouBao_API

from assistant.business import encode_image
from assistant.usage import Usage
from llm.client.deepseek_api import deepseek_api, DeepSeek_API

class BaseChatRunTime(object):
    provider = None
    common_model = 'gpt-3.5-turbo'

    ROLE_ASSISTANT_USER = 'assistant_user'

    def __init__(self, request, chat, assistant, content=None, message=None, new_flag=None, soucre_assistant=None,is_users_speak=None, **kwargs):
        self.request = request
        self.chat = chat
        self.assistant = assistant
        self.content = content
        self.message = message
        self.new_flag = new_flag
        #self.chat_assistant = chat_assistant

        self.soucre_assistant = soucre_assistant
        self.is_users_speak = is_users_speak

        self.arguments = ''
        self.function_name = ''
        self.tool_call_id = ''
        self.tool_call_messages = []
        self.contents = []

        self.client_api = None

        self.has_save_user_content = False

        self.references = None
        

        self.chat_options = kwargs.get('chat_options')
        self.__kwargs = kwargs

    def _get_assistant_data(self, assistant=None):
        if assistant is None:
            assistant = self.assistant
        return {
            'uuid': str(assistant.uuid),
            'id': assistant.id,
            'name': assistant.name,
            'avatar_url': assistant.avatar.url if assistant.avatar  else ''
        }


    def pre_limit_message(self):
        send_messages = self.pre_system_message()
        chat_messages = []
        if self.chat.messages:
            chat_messages = json.loads(self.chat.messages)

        user_messages = []
        chat_msg_length = len(chat_messages)
        if chat_msg_length > 1:
            user_messages = chat_messages[0:]
            msg_limit = self.assistant.message_limit
            if msg_limit is None or msg_limit <= 0:
                msg_limit = 5
            if msg_limit and msg_limit > 0 and msg_limit < len(chat_messages):
                start = 0 - msg_limit
                first_msg = user_messages[start]
                if first_msg.get('role') == 'tool':
                    history_msgs = user_messages[start - 1:]
                else:
                    history_msgs = user_messages[start:]
                send_messages.extend(history_msgs)
            else:
                send_messages.extend(user_messages)
        return send_messages

    def format_content(self, content):
        return content

    def format_message(self, message):
        return message

    def pre_format_message(self, send_messages):
        messages = []
        for send_msg in send_messages:
            if send_msg.get('assistant'):
                send_msg.pop('assistant', None)
            if send_msg.get('references'):
                send_msg.pop('references', None)
            if send_msg.get('role') == self.ROLE_ASSISTANT_USER:
                send_msg['role'] = 'user'

            send_msg = self.format_message(send_msg)
            if not send_msg:
                continue
            old_contents = send_msg.get('content')
            if old_contents:
                contents = []
                for old_content in old_contents:
                    content = self.format_content(old_content)
                    if content:
                        contents.append(content)
                send_msg['content'] = contents
            messages.append(send_msg)
        return messages


    def pre_chat_completions(self):
        send_messages = self.pre_limit_message()

        if self.content:
            content_openai = json.loads(json.dumps(self.content))
            send_messages.append({
                'role': 'user',
                'content': content_openai,
            })

        send_messages = self.pre_format_message(send_messages)

        return send_messages
    def pre_chat_completions_assistant(self,chat_assistant):
        send_messages = self.pre_limit_message()

        if self.content:
            content_openai = json.loads(json.dumps(self.content))
            send_messages.append({
                'role': 'assistant',
                'assistant': chat_assistant,
                'content': content_openai,
            })

        send_messages = self.pre_format_message(send_messages)

        return send_messages



    def chat_completions(self, send_messages):
        assistant = self.assistant
        tools = None
        if assistant.llm and assistant.llm.can_toolcall:
            if assistant.tools:
                tools = json.loads(assistant.tools)
            if assistant.enable_search:
                ff = os.path.join(settings.BASE_DIR, 'assistant/function_tools/enable_search.json')
                with open(ff) as fp:
                    search_json = json.load(fp)
                    if isinstance(tools, list):
                        tools.extend(search_json)
                    else:
                        tools = search_json

        # print('\n\n-------------------')
        # for s in send_messages:
        #     print(s)
        # print('-------------------\n\n')
        # print(self.assistant.model)

        model = assistant.llm.value if assistant.llm and assistant.llm.value else assistant.model
        run_stream = self.client_api.chat_completions(send_messages,
            system=self.assistant.instructions,
            model=model,
            stream=True,
            temperature=assistant.temperature,
            top_p=assistant.top_p,
            presence_penalty=assistant.presence_penalty,
            max_tokens=assistant.max_tokens,
            frequency_penalty=assistant.frequency_penalty,
            tools=tools,
            llm=assistant.llm
        )
        return run_stream


    def content_block_stop(self):
        chat = self.chat
        content = self.content
        msg = ''.join(self.contents)

        assistant_msg = {
            'role': 'assistant',
            'assistant': self._get_assistant_data(),
            'content': [{
                'type': 'text',
                'text': msg
            }]
        }

        if self.references:
            assistant_msg['references'] = self.references

        messages = []
        if chat.messages:
            messages = json.loads(chat.messages)

        if content and not self.has_save_user_content:
            if self.is_users_speak or self.is_users_speak is None:
                print("不需要保存用户的数据")
            elif self.soucre_assistant is None:
                user_msg = {
                    'role': 'user',
                    'content': content
                }
                messages.append(user_msg)
            else:
                user_msg = {
                    'role': self.ROLE_ASSISTANT_USER,
                    'assistant': self._get_assistant_data(self.soucre_assistant),
                    'content': content
                }
                messages.append(user_msg)

        self.has_save_user_content = True
        messages.append(assistant_msg)
        chat.messages = json.dumps(messages)
        chat.save()

        if not chat.name:
            title_msgs = self.pre_limit_message()
            title_msg = []
            for i in title_msgs:
                r = i.get('role')
                content = i.get('content')
                t_cc = []
                if not content:
                    continue
                for cc in content:
                    if not isinstance(cc, dict):
                        continue
                    if cc.get('type') == 'text':
                        t_cc.append(cc)

                i['content'] = t_cc
                if r == 'user' or r == 'system':
                    title_msg.append(i)
                elif r == 'assistant' and not i.get('tool_calls'):
                    if i.get('assistant'):
                        i.pop('assistant', None)
                    title_msg.append(i)

            name = self.client_api.generate_title(title_msg, self.common_model)
            chat.name = name

        chat.save()
        return

    def save_assistant(self,content):
        chat = self.chat
        assistant_msg = {
            'role': 'assistant',
            'assistant': self._get_assistant_data(),
            'content': [{
                'type': 'text',
                'text': content
            }]
        }
        messages = []
        messages.append(assistant_msg)
        chat.save()
        return

    def do_completed(self):
        msg = ''.join(self.contents)
        assistant_msg = {
            'role': 'assistant',
            'assistant': self._get_assistant_data(),
            'content': [{
                'type': 'text',
                'text': msg
            }],
            'references': self.references
        }
        chat = self.chat
        chat_data = ChatSerializer(chat).data
        data = json.dumps({'success': True, 'usageCheck': True, 'event': 'completed', 'chat': chat_data, 'stream': assistant_msg})
        return data



    def tool_calls(self):
        messages = []
        chat = self.chat
        if chat.messages:
            messages = json.loads(chat.messages)

        if self.content and not self.has_save_user_content:
            messages.append({
                'role': 'user',
                'content': self.content
            })


        logging.info('function call arguments: {}'.format(self.arguments))
        parse_error = False
        try:
            args = json.loads(self.arguments)
        except Exception:
            res = '解析函数参数错误，请训练后重新提交请求'
            logging.exception('json load error: {}'.format(self.arguments))
            parse_error = True
            args = {}

        if not parse_error:
            chat_options = self.__kwargs.get('chat_options')
            if chat_options:
                logging.info('function call chat_options is {}'.format(chat_options))
                args.update(chat_options)
            try:
                logging.info('excute function {}(request, {})'.format(self.function_name, args))
                ret, res = call_function(self.function_name, self.request, args)
            except Exception:
                res = '{} 执行错误，参数 {}'.format(self.function_name, args)
                logging.exception('tool_call_id {} excute function {} error'.format(self.tool_call_id, self.function_name))


        msg = {
            'role': 'assistant',
            'assistant': self._get_assistant_data(),
            'tool_calls': [{
                'function': {
                    'name': self.function_name,
                    'arguments': json.dumps(args) if not parse_error else self.arguments
                },
                'id': self.tool_call_id,
                'type': 'function'
            }]
        }
        messages.append(msg)


        call_msg = {
            'role': 'tool',
            'assistant': self._get_assistant_data(),
            'content': [{
                'text': json.dumps({'result': res}, indent=4, ensure_ascii=False),
                'type': 'text'
            }], 
            'tool_call_id': self.tool_call_id
        }
        messages.append(call_msg)

        chat.messages = json.dumps(messages)
        chat.save()
        self.has_save_user_content = True
        return msg, call_msg


    def do_progressing(self, chunk):
        stream = self.format_progressing_stream_data(chunk)
        data = json.dumps({'success': True, 'usageCheck': True, 'event': 'in_progress', 'stream': stream})
        return data

    def do_tool_calls(self):
        res = self.tool_calls()
        chat = self.chat
        chat_data = ChatSerializer(chat).data
        data = json.dumps({'success': True, 'usageCheck': True, 'event': 'call_function', 'stream': res, 'chat': chat_data})
        return data

    def do_chunk(self, chunk):
        raise NotImplementedError("do_chunk not implemented!")

    def format_progressing_stream_data(self, chunk):
        raise NotImplementedError("format_progressing_stream_data not implemented!")

    def pre_system_message(self):
        send_messages = []
        if self.assistant.instructions:
            system_message = {
                'role': 'system',
                'content': [{
                    'text': self.assistant.instructions,
                    'type': 'text'
                }]
            }
            send_messages.append(system_message)
        return send_messages


    def count_token_usage(self, usage):
        chat = self.chat
        if not chat.messages:
            return
        llm = self.assistant.llm
        amount = usage.get_amount(llm)

        usage_billing = UsageBilling(
            user=self.chat.user,
            llm=llm,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            prompt_amount=amount.get('prompt_amount'),
            completion_amount=amount.get('completion_amount'),
            currency_code=llm.currency_code,
            llm_name=llm.name
        )
        usage_billing.save()
        
        
        messages = json.loads(chat.messages)
        message = messages[-1]
        message['usage_billing_uuid'] = str(usage_billing.uuid)
        chat.messages = json.dumps(messages)
        chat.save()


class OpenAIChatRunTime(BaseChatRunTime):

    def __init__(self, request, chat, assistant, content=None, message=None, new_flag=None, **kwargs):
        super().__init__(
            request=request,
            chat=chat,
            assistant=assistant,
            content=content,
            message=message,
            new_flag=new_flag,
            **kwargs
        )

        if self.provider:
            self.client_api = OpenAI_API(api_key=self.provider.api_key, base_url=self.provider.base_url, organization=self.provider.organization_id, project=self.provider.project_id)
        else:
            self.client_api = openai_api

    def format_progressing_stream_data(self, chunk):
        choice = chunk.choices[0]
        self.contents.append(choice.delta.content)
        return chunk.to_dict()

    def format_content(self, content):
        if content.get('type') == 'image_url':
            url_path = content.get('image_url').get('url_path')
            media_type, _ = mimetypes.guess_type(url_path)
            image_file = os.path.join(settings.MEDIA_ROOT, url_path)
            image_data = encode_image(image_file, url_flag=False)
            content['image_url']['url'] = f"data:{media_type};base64,{image_data}"
        return content


    def pre_system_message(self):
        send_messages = []
        if self.assistant.instructions:
            system_message = {
                'role': 'system',
                'content': [{
                    'text': self.assistant.instructions,
                    'type': 'text'
                }]
            }
            send_messages.append(system_message)
        return send_messages


    def _pre_tool_calls(self, choice):
        tool_calls = choice.delta.tool_calls
        self.arguments += tool_calls[0].function.arguments
        if not self.function_name:
            self.function_name = tool_calls[0].function.name
        if not self.tool_call_id:
            self.tool_call_id = tool_calls[0].id


    def do_chunk(self, chunk):
        if chunk.usage:
            usage = chunk.usage
            u = Usage(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)
            return self.count_token_usage(u)

        choice = chunk.choices[0]
        if choice.finish_reason == 'tool_calls':
            return self.do_tool_calls()
        if choice.finish_reason == 'stop':
            self.content_block_stop()
            return self.do_completed()
        if choice.delta.tool_calls:
            self._pre_tool_calls(choice)
        return self.do_progressing(chunk)


class AnthropicChatRunTime(BaseChatRunTime):
    def __init__(self, request, chat, assistant, content=None, message=None, new_flag=None, **kwargs):
        super().__init__(
            request=request,
            chat=chat,
            assistant=assistant,
            content=content,
            message=message,
            new_flag=new_flag,
            **kwargs
        )

        if self.provider:
            self.client_api = Anthropic_API(api_key=self.provider.api_key, base_url=self.provider.base_url)
        else:
            self.client_api = anthropic_api

    def pre_system_message(self):
        return []

    def format_progressing_stream_data(self, chunk):
        self.contents.append(chunk.delta.text)
        stream = {
            'choices': [{
                'delta': {
                    'content': chunk.delta.text
                }
            }]
        }
        return stream

    def format_message(self, message):
        if message.get('role') == 'assistant' and message.get('tool_calls'):
            tool_call = message.get('tool_calls')[0]
            message = {
                'role': 'assistant',
                'content': [{
                    'type': 'tool_use',
                    'id': tool_call.get('id'),
                    'name': tool_call.get('function').get('name'),
                    'input': json.loads(tool_call.get('function').get('arguments'))
                }]
            }
        elif message.get('role') == 'tool':
            message = {
                'role': 'user',
                'content': [{
                    'type': 'tool_result',
                    'tool_use_id': message.get('tool_call_id'),
                    'content': message.get('content')[0].get('text')
                }]
            }

        return message

    def format_content(self, content):
        if content.get('type') == 'image_url':
            url_path = content.get('image_url').get('url_path')
            media_type, _ = mimetypes.guess_type(url_path)
            image_file = os.path.join(settings.MEDIA_ROOT, url_path)
            image_data = encode_image(image_file, url_flag=False)
            content = {
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': media_type,
                    'data': image_data
                }
            }
        return content

    def _pre_tool_calls(self, chunk):
        if not self.tool_call_id:
            self.tool_call_id = chunk.content_block.id
        if not self.function_name:
            self.function_name = chunk.content_block.name


    def _pre_do_tool_call_arguments(self, chunk):
        self.arguments += chunk.delta.partial_json


    def do_chunk(self, chunk):
        _type = chunk.type
        if _type == 'message_start':
            pass
        elif _type == 'content_block_start':
            if chunk.content_block.type == 'tool_use':
                self._pre_tool_calls(chunk)
        elif _type == 'content_block_delta':
            if chunk.delta.type == 'input_json_delta':
                self._pre_do_tool_call_arguments(chunk)
            elif chunk.delta.type == 'text_delta':
                return self.do_progressing(chunk)
        elif _type == 'content_block_stop' and not self.tool_call_id:
            self.content_block_stop()
        elif _type == 'message_delta':
            if chunk.delta.stop_reason == 'tool_use':
                return self.do_tool_calls()
        elif _type == 'message_stop' and not self.tool_call_id:
            return self.do_completed()




class DouBaoRunTime(BaseChatRunTime):
    def __init__(self, request, chat, assistant, content=None, message=None, new_flag=None, **kwargs):
        super().__init__(
            request=request,
            chat=chat,
            assistant=assistant,
            content=content,
            message=message,
            new_flag=new_flag,
            **kwargs
        )

        if self.provider:
            self.client_api = DouBao_API(api_key=self.provider.api_key, base_url=self.provider.base_url)
        else:
            self.client_api = doubao_api


    def format_progressing_stream_data(self, chunk):
        choice = chunk.choices[0]
        self.contents.append(choice.delta.content)
        return chunk.to_dict()

    def format_content(self, content):
        if content.get('type') == 'image_url':
            url_path = content.get('image_url').get('url_path')
            media_type, _ = mimetypes.guess_type(url_path)
            image_file = os.path.join(settings.MEDIA_ROOT, url_path)
            image_data = encode_image(image_file, url_flag=False)
            content['image_url']['url'] = f"data:{media_type};base64,{image_data}"
        return content

    def _pre_tool_calls(self, choice):
        tool_calls = choice.delta.tool_calls
        function = tool_calls[0].function
        if not self.arguments:
            self.arguments = function.arguments
        if not self.function_name:
            self.function_name = function.name
        if not self.tool_call_id:
            self.tool_call_id = tool_calls[0].id

    def do_chunk(self, chunk):
        if chunk.usage:
            usage = chunk.usage
            u = Usage(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)
            return self.count_token_usage(u)

        choice = chunk.choices[0]
        if hasattr(chunk, 'references') and chunk.references:
            references = []
            for item in chunk.references:
                references.append({
                    'url': item.url,
                    'site_name': item.site_name,
                    'title': item.title
                })
            self.references = references
        if choice.finish_reason == 'tool_calls':
            self._pre_tool_calls(choice)
            if not self.function_name and not self.arguments and not self.tool_call_id:
                return ''
            return self.do_tool_calls()
        if choice.finish_reason == 'stop':
            self.content_block_stop()
            return self.do_completed()
        if choice.delta.tool_calls:
            self._pre_tool_calls(choice)
        return self.do_progressing(chunk)


class DeepSeekRunTime(BaseChatRunTime):
    def __init__(self, request, chat, assistant, content=None, message=None, new_flag=None, **kwargs):
        super().__init__(
            request=request,
            chat=chat,
            assistant=assistant,
            content=content,
            message=message,
            new_flag=new_flag
        )

        if self.provider:
            self.client_api = DeepSeek_API(api_key=self.provider.api_key, base_url=self.provider.base_url)
        else:
            self.client_api = deepseek_api

    def format_progressing_stream_data(self, chunk):
        choice = chunk.choices[0]
        self.contents.append(choice.delta.content)
        return chunk.to_dict()

    def do_chunk(self, chunk):
        choice = chunk.choices[0]
        if choice.finish_reason == 'tool_calls':
            return self.do_tool_calls()
        if choice.finish_reason == 'stop':
            self.content_block_stop()
            return self.do_completed()
        if choice.delta.tool_calls:
            self._pre_tool_calls(choice)
        return self.do_progressing(chunk)

    def format_content(self, content):
        if content.get('type') == 'image_url':
            url_path = content.get('image_url').get('url_path')
            media_type, _ = mimetypes.guess_type(url_path)
            image_file = os.path.join(settings.MEDIA_ROOT, url_path)
            image_data = encode_image(image_file, url_flag=False)
            content['image_url']['url'] = f"data:{media_type};base64,{image_data}"
        return content

    def _pre_tool_calls(self, choice):
        tool_calls = choice.delta.tool_calls
        self.arguments += tool_calls[0].function.arguments
        if not self.function_name:
            self.function_name = tool_calls[0].function.name
        if not self.tool_call_id:
            self.tool_call_id = tool_calls[0].id


class QwenChatRunTime(OpenAIChatRunTime):
    common_model = 'qwen-plus'
    pass


RUNTIME_MAPS = {
    'openai': OpenAIChatRunTime,
    'anthropic': AnthropicChatRunTime,
    'doubao': DouBaoRunTime,
    'deepseek': DeepSeekRunTime,
    'qwen': QwenChatRunTime
}


def get_runtime(assistant):
    if assistant.llm and assistant.llm.provider:
        service_provider = assistant.llm.provider.value
    else:
        service_provider = assistant.service_provider
    if service_provider not in RUNTIME_MAPS:
        raise Exception('not found service provider: {}'.format(service_provider))
    run_time_object = RUNTIME_MAPS.get(service_provider)

    if assistant.llm and assistant.llm.provider:
        run_time_object.provider = assistant.llm.provider
    return run_time_object



def get_runtime1(service_provider):
    if service_provider in RUNTIME_MAPS:
        return RUNTIME_MAPS.get(service_provider)
    raise Exception('not found service provider: {}'.format(service_provider))

