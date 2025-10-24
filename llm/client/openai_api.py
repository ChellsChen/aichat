import time
from pathlib import Path

from openai import OpenAI

from django.conf import settings

class OpenAI_API(object):
    def __init__(self, api_key, base_url, project, organization):
    	self.client = OpenAI(api_key=api_key, base_url=base_url, project=project, organization=organization)

    def create_assistant(self, name, instructions, description=None, tools=[], model="gpt-3.5-turbo-1106", top_p=None, temperature=None):
        assistant = self.client.beta.assistants.create(
            name=name,
            description=description,
            instructions=instructions,
            tools=tools,
            model=model,
            top_p=top_p,
            temperature=temperature
        )
        return assistant

    def get_assistant(self, assistant_id):
        assistant = self.client.beta.assistants.retrieve(assistant_id)
        return assistant

    def update_assistant(self, assistant_id, instructions=None, model=None, top_p=None, temperature=None):
        assistant = self.client.beta.assistants.update(assistant_id, 
            instructions=instructions,
            model=model,
            top_p=top_p,
            temperature=temperature
        )
        return assistant

    def list_assistant(self, limit=None, after=None, before=None):
        return self.client.beta.assistants.list()

    def delete_assistant(self, assistant_id):
        return self.client.beta.assistants.delete(assistant_id)

    def create_thread(self):
        thread = self.client.beta.threads.create()
        return thread

    def delete_thread(self, thread_id):
        return self.client.beta.threads.delete(thread_id)

    def list_messages(self, thread_id, limit=50, after=None):
        datas = self.client.beta.threads.messages.list(thread_id, limit=limit, after=after)
        return datas

    def upload_file(self, filpath, purpose):
        datas = self.client.files.create(file=Path(filpath), purpose=purpose)
        return datas

    def chat_completions(self, messages, model='gpt-3.5-turbo', stream=False,
            temperature=1, top_p=1, presence_penalty=0, max_tokens=None, frequency_penalty=0, tools=None, **kwargs):
        stream_options = None
        if stream:
            stream_options = {'include_usage': True}
        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            top_p=top_p,
            presence_penalty=presence_penalty,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            tools=tools,
            stream_options=stream_options
        )
        return completion


    def get_title(self, user_msg, assistant_msg):
        content = '使用四到五个字直接返回这段对话句话的简要主题，不要解释、不要标点、不要语气词、不要多余文本，不要加粗，如果没有主题，请直接返回“闲聊”'
        messages = [{
            'role': 'user',
            'content': [{
                'type': 'text',
                'text': user_msg
            }]
        }, {
            'role': 'assistant',
            'content': [{
                'type': 'text',
                'text': assistant_msg
            }]
        }, {
            'role': 'user',
            'content': [{
                'type': 'text',
                'text': content
            }]
        }]
        completion = self.client.chat.completions.create(
          model='gpt-3.5-turbo',
          messages=messages
        )
        title = completion.choices[0].message.content
        return title

    def generate_title(self, messages):
        content = '使用四到五个字直接返回这段对话句话的简要主题，不要解释、不要标点、不要语气词、不要多余文本，不要加粗，如果没有主题，请直接返回“闲聊”'
        message = {
            'role': 'user',
            'content': [{
                'type': 'text',
                'text': content
            }]
        }
        messages.append(message)
        completion = self.client.chat.completions.create(
          model='gpt-3.5-turbo',
          messages=messages
        )
        title = completion.choices[0].message.content
        return title


    def start_chat_by_stream(self, assistant_id, content, thread_id, attachments=None):
        message_params = {
            "thread_id": thread_id,
            "role": "user", 
            "content": content
        }
        if attachments:
            message_params['attachments'] = attachments
        self.client.beta.threads.messages.create(**message_params)

        return self.client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id, stream=True)


    def start_chat(self, assistant_id, content, thread_id, attachments=None):
        message_params = {
            "thread_id": thread_id,
            "role": "user", 
            "content": content
        }
        if attachments:
            message_params['attachments'] = attachments
        self.client.beta.threads.messages.create(**message_params)

        run = self.client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)

        while run.status != 'completed':
            time.sleep(0.05)
            run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        response = self.client.beta.threads.messages.list(thread_id)
        first_id = response.first_id
        for item in response.data:
            if item.id == first_id:
                return item

        return []

openai_api = OpenAI_API(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL, project=settings.OPENAI_PROJECT, organization=settings.OPENAI_ORGANIZATION)




        





