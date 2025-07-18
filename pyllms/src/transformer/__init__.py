from .anthropic_transformer import AnthropicTransformer
from .gemini_transformer import GeminiTransformer
from .deepseek_transformer import DeepseekTransformer
from .tooluse_transformer import TooluseTransformer
from .openrouter_transformer import OpenrouterTransformer
from .maxtoken_transformer import MaxTokenTransformer
from .groq_transformer import GroqTransformer
from .openai_transformer import OpenAITransformer

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

# Create transformer dictionary for TransformerService to use
# This matches the structure in TypeScript's transformer/index.ts
transformers = {
    "AnthropicTransformer": AnthropicTransformer,
    "GeminiTransformer": GeminiTransformer,
    "DeepseekTransformer": DeepseekTransformer,
    "TooluseTransformer": TooluseTransformer,
    "OpenrouterTransformer": OpenrouterTransformer,
    # "MaxTokenTransformer": MaxTokenTransformer,
    "GroqTransformer": GroqTransformer,
    "OpenAITransformer": OpenAITransformer
}