from .anthropic_transformer import AnthropicTransformer
from .gemini_transformer import GeminiTransformer
from .deepseek_transformer import DeepseekTransformer
from .tooluse_transformer import TooluseTransformer
from .openrouter_transformer import OpenrouterTransformer
from .maxtoken_transformer import MaxTokenTransformer
from .groq_transformer import GroqTransformer
from .openai_transformer import OpenAITransformer

# Export all transformer classes
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
    # "AnthropicTransformer": AnthropicTransformer,
    # "GeminiTransformer": GeminiTransformer,
    # "DeepseekTransformer": DeepseekTransformer,
    # "TooluseTransformer": TooluseTransformer,
    # "OpenrouterTransformer": OpenrouterTransformer,
    # "MaxTokenTransformer": MaxTokenTransformer,
    # "GroqTransformer": GroqTransformer,
    # OpenAITransformer is included in Python for compatibility
    # It's not in the TypeScript index.ts but exists as a separate file
    "OpenAITransformer": OpenAITransformer
}