
from openai import OpenAI
from django.conf import settings

class DeepSeek_API(object):
    def __init__(self, api_key, base_url):
        self.client = OpenAI(api_key=api_key, base_url=base_url)

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
        messages = self.__format_messages(messages)
        completion = self.client.chat.completions.create(
            model='deepseek-chat',
            messages=messages,
            max_tokens=1024,
            stream=False
        )
        title = '闲聊'
        if len(completion.choices) > 0:
            title = completion.choices[0].message.content
        return title

    def chat_completions(self, messages, model='deepseek-chat', stream=False,
            temperature=1, top_p=1, presence_penalty=0, max_tokens=None, frequency_penalty=0, tools=None, llm=None,**kwargs):

        messages = self.__format_messages(messages, can_vision=llm.can_vision)

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
        )
        return completion


deepseek_api = DeepSeek_API(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)


def main():
    client = OpenAI(api_key="sk-6544c928a00b478ca6191b4a3d7aba63", base_url="https://api.deepseek.com/v1")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ],
        stream=False
    )

    print(response.choices[0].message.content)

if __name__ == '__main__':
    main()

