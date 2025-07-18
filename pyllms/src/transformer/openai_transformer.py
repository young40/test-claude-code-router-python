from typing import Optional

from ..types.transformer import Transformer, TransformerOptions


class OpenAITransformer(Transformer):
    """OpenAI transformer"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "OpenAI"
        self.end_point = "/v1/chat/completions"