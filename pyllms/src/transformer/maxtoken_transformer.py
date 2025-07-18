from typing import Optional, Union, Dict, Any

from ..types.transformer import Transformer, TransformerOptions, TransformRequestResult
from ..types.llm import UnifiedChatRequest, LLMProvider


class MaxTokenTransformer(Transformer):
    """MaxToken Transformer - Limits the maximum tokens in a request"""
    
    TransformerName = "maxtoken"
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.max_tokens = self.options.get("max_tokens") if self.options else None
    
    async def transform_request_in(
        self, 
        request: Union[UnifiedChatRequest, Dict[str, Any]], 
        provider: LLMProvider = None
    ) -> Union[Dict[str, Any], TransformRequestResult]:
        """Transform request input, limiting the maximum token count"""
        # Convert request to dict if it's an object
        request_dict = request.__dict__ if hasattr(request, '__dict__') else request
        
        # Apply max token limit if needed
        if request_dict.get('max_tokens') and self.max_tokens and request_dict['max_tokens'] > self.max_tokens:
            request_dict['max_tokens'] = self.max_tokens
        
        return request_dict