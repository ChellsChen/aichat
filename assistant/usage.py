

class Usage(object):
    UNIT_CARRY = 1000000

    def __init__(self, prompt_tokens, completion_tokens, total_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

    def __str__(self):
        return 'Usage(prompt_tokens={}, completion_tokens={}, total_tokens={})'.format(self.prompt_tokens, self.completion_tokens, self.total_tokens)

    def to_dict(self):
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens
        }

    def get_amount(self, llm):
        number_dict = {
            llm.PRICE_NUMBER_M: 1000000,
            llm.PRICE_NUMBER_K: 1000
        }
        prompt_price = float(llm.prompt_price)
        completion_amount = float(llm.completion_price)
        tokens_count = number_dict.get(llm.tokens_count)
        prompt_amount = (self.prompt_tokens / tokens_count ) * prompt_price * self.UNIT_CARRY
        completion_amount = (self.completion_tokens / tokens_count ) * completion_amount * self.UNIT_CARRY

        return {
            'prompt_amount': prompt_amount,
            'completion_amount': completion_amount
        }