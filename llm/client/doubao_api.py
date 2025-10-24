from volcenginesdkarkruntime import Ark
from django.conf import settings

class DouBao_API(object):
    def __init__(self, api_key, base_url):
        self.client = Ark(api_key=api_key, base_url=base_url)

    def __format_messages(self, messages, can_vision=False):
        for msg in messages:
            content = msg.get('content')
            if isinstance(content, str):
                continue
            if isinstance(content, list):
                if len(content) == 1:
                    text = content[0].get('text')
                    msg['content'] = text
        return messages


    def generate_title(self, messages):
        system_prompt = '使用四到五个字直接返回这段对话句话的简要主题，不要解释、不要标点、不要语气词、不要多余文本，不要加粗'
        messages.append({
            'role': 'user',
            'content': [{
                'text': system_prompt,
                'type': 'text'
            }]
        })
        model = settings.DOUBAO_DEFAULT_MODEL
        messages = self.__format_messages(messages)
        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
            stream=False
        )
        title = '闲聊'
        if len(completion.choices) > 0:
            title = completion.choices[0].message.content
        return title


    def chat_completions(self, messages, model='', stream=False,
            temperature=1, top_p=1, max_tokens=4096, tools=None, llm=None, **kwargs):
        
        messages = self.__format_messages(messages, can_vision=llm.can_vision)
        if 'bot' in model:
            client = self.client.bot_chat
        else:
            client = self.client.chat

        stream_options = {'include_usage': True}

        completion = client.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            tools=tools,
            stream_options=stream_options
        )
        return completion

doubao_api = DouBao_API(api_key=settings.DOUBAO_API_KEY, base_url=settings.DOUBAO_BASE_URL)


if __name__ == '__main__':
    doubao_api = DouBao_API(api_key='dea73620-f77e-4cc0-af39-4fc0771b2704', base_url='https://ark.cn-beijing.volces.com/api/v3')
    system = 'you are a helpful assistant'
    messages = [{
        'role': 'system',
        'content': 'you are a helpful assistant'
    },{
        'role': 'user',
        'content': [{
            'text': '帮我分析网页：https://www.volcengine.com/docs/82379/1285207#messageparam',
            'type': 'text'
        },]
    }]
    res = doubao_api.chat_completions(messages=messages, stream=True, model='ep-20241209112050-lp69k')
    #print(res)
    for chunk in res:
        #print(chunk)
        print(chunk.choices[0].delta.content, end='')
        #print(chunk.to_dict())
        # if (chunk.type == 'content_block_delta'):
        #     print(chunk.delta.text)
    #print(res.content[0].text)
