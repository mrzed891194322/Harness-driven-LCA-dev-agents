import os
from dotenv import load_dotenv


def load_embedding_config():
    """
    加载并验证从环境变量配置的嵌入（embedding）相关 API 参数。

    返回:
        tuple: (api_key, api_url, model_name)
    """
    load_dotenv()
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_url = os.getenv("EMBEDDING_API_URL")
    model_name = os.getenv("EMBEDDING_MODEL")

    if not api_key or api_key == "sk-your-api-key-here":
        raise ValueError("Please set a valid EMBEDDING_API_KEY in .env")

    return api_key, api_url, model_name