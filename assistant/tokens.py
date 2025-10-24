import tiktoken



def num_tokens_from_string(string: str, encoding_name: str, model_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

if __name__ == '__main__':
    num = num_tokens_from_string("你好呀", "cl100k_base")
    print(num)




