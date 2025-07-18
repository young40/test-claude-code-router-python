from typing import Optional

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest


class MaxTokenTransformer(Transformer):
    """最大Token限制转换器"""
    
    TransformerName = "maxtoken"
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.max_tokens = options.get("max_tokens") if options else None
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider=None
    ) -> UnifiedChatRequest:
        """转换请求输入，限制最大token数"""
        if (hasattr(request, 'max_tokens') and 
            request.max_tokens and 
            self.max_tokens and 
            request.max_tokens > self.max_tokens):
            request.max_tokens = self.max_tokens
        
        return request