
import anthropic
from django.conf import settings

class Anthropic_API(object):
    def __init__(self, api_key, base_url):
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)


    def __format_tools(self, tools):
        results = []
        for index, item in enumerate(tools):
            function = item.get('function')
            res = {
                'name': function.get('name'),
                'description': function.get('description')
            }
            parameters = function.get('parameters')
            if parameters:
                input_schema = {
                    'type': parameters.get('type'),
                    'properties': parameters.get('properties')
                }
                if parameters.get('required'):
                    input_schema['required'] = parameters.get('required')
                res['input_schema'] = input_schema
                
            results.append(res)
        return results

    def generate_title(self, messages):
        system_prompt = '使用四到五个字直接返回这段对话句话的简要主题，不要解释、不要标点、不要语气词、不要多余文本，不要加粗'
        messages.append({
            'role': 'user',
            'content': [{
                'text': system_prompt,
                'type': 'text'
            }]
        })
        completion = self.client.messages.create(
            #system='用四到五个字帮我概括对话的的主题',
            model='claude-3-5-sonnet-20241022',
            messages=messages,
            max_tokens=1024
        )
        title = 'dadad'
        if len(completion.content) > 0:
            title = completion.content[0].text
        return title


    def chat_completions(self, messages, model='claude-3-5-sonnet-20241022', system=None, stream=False,
        temperature=1, top_p=1, max_tokens=4096, tools=None, **kwargs):
        if not tools:
            tools = []
        if tools:
            tools = self.__format_tools(tools)
        if not system:
            system = ''
        completion = self.client.messages.create(
            system=system,
            model=model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            tools=tools,
        )
        return completion



anthropic_api = Anthropic_API(api_key=settings.ANTHROPIC_API_KEY, base_url=settings.ANTHROPIC_BASE_URL)



if __name__ == '__main__':
    anthropic_api = Anthropic_API(api_key='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', base_url='http://anthropic-api.qiwuai.cn')
    system = 'you are a helpful assistant'
    messages = [{
        'role': 'user',
        'content': [{
            'text': 'hello world',
            'type': 'text'
        },]
    }]
    res = anthropic_api.chat_completions(messages=messages, system=system, stream=True)
    #print(res)
    for chunk in res:
        print(chunk)
        #print(chunk.to_dict())
        if (chunk.type == 'content_block_delta'):
            print(chunk.delta.text)
    #print(res.content[0].text)
