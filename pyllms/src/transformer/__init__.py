from .anthropic_transformer import AnthropicTransformer
from .gemini_transformer import GeminiTransformer
from .deepseek_transformer import DeepseekTransformer
from .tooluse_transformer import TooluseTransformer
from .openrouter_transformer import OpenrouterTransformer
from .maxtoken_transformer import MaxTokenTransformer
from .groq_transformer import GroqTransformer
from .openai_transformer import OpenAITransformer

# 导出所有转换器类
__all__ = [
    "AnthropicTransformer",
    "GeminiTransformer", 
    "DeepseekTransformer",
    "TooluseTransformer",
    "OpenrouterTransformer",
    "MaxTokenTransformer",
    "GroqTransformer",
    "OpenAITransformer",
    "transformers"
]

# 创建转换器字典，供 TransformerService 使用
transformers = {
    "AnthropicTransformer": AnthropicTransformer,
    "GeminiTransformer": GeminiTransformer,
    "DeepseekTransformer": DeepseekTransformer,
    "TooluseTransformer": TooluseTransformer,
    "OpenrouterTransformer": OpenrouterTransformer,
    "MaxTokenTransformer": MaxTokenTransformer,
    "GroqTransformer": GroqTransformer,
    "OpenAITransformer": OpenAITransformer
}