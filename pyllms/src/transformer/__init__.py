from .anthropic_transformer import AnthropicTransformer
from .openai_transformer import OpenAITransformer

# 导出所有转换器
transformers = {
    "AnthropicTransformer": AnthropicTransformer,
    "OpenAITransformer": OpenAITransformer,
}

def get_default_transformers():
    """获取默认转换器列表"""
    return list(transformers.values())