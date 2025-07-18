import importlib
import sys
from typing import Dict, List, Optional, Any, Union, Callable, Type

from ..utils.log import log
from .config import ConfigService
from ..types.transformer import Transformer, TransformerConstructor


class TransformerService:
    """Transformer service class, responsible for managing transformers"""
    
    def __init__(self, config_service: ConfigService):
        self.config_service = config_service
        self.transformers: Dict[str, Union[Transformer, TransformerConstructor]] = {}
    
    def register_transformer(self, name: str, transformer: Union[Transformer, TransformerConstructor]) -> None:
        """Register a transformer"""
        # If it's a class with TransformerName static property, register it as is
        if hasattr(transformer, 'TransformerName') and isinstance(transformer.TransformerName, str):
            self.transformers[name] = transformer
            log(f"register transformer: {name} (class with TransformerName)")
            return
            
        # If it's a callable (class) and not an instance, try to instantiate it
        if callable(transformer) and not hasattr(transformer, 'end_point'):
            try:
                # Try to instantiate the transformer class
                instance = transformer()
                self.transformers[name] = instance
                endpoint_info = f" (endpoint: {instance.end_point})" if hasattr(instance, 'end_point') and instance.end_point else " (no endpoint)"
                log(f"register transformer: {name}{endpoint_info}")
                return
            except Exception as e:
                # If instantiation fails, register the class as is
                log(f"Error instantiating transformer {name}: {e}")
                self.transformers[name] = transformer
                return
        
        # Register the transformer as is (already an instance)
        self.transformers[name] = transformer
        endpoint_info = f" (endpoint: {transformer.end_point})" if hasattr(transformer, 'end_point') and transformer.end_point else " (no endpoint)"
        log(f"register transformer: {name}{endpoint_info}")
    
    def get_transformer(self, name: str) -> Optional[Union[Transformer, TransformerConstructor]]:
        """Get a transformer by name"""
        return self.transformers.get(name)
    
    def get_all_transformers(self) -> Dict[str, Union[Transformer, TransformerConstructor]]:
        """Get all transformers"""
        return self.transformers.copy()
    
    def get_transformers_with_endpoint(self) -> List[Dict[str, Any]]:
        """Get transformers with endpoints"""
        result = []
        
        for name, transformer in self.transformers.items():
            # Check if the transformer is an instance with an endpoint
            if hasattr(transformer, 'end_point') and transformer.end_point:
                result.append({"name": name, "transformer": transformer})
            # Check if it's a transformer class that needs to be instantiated
            elif callable(transformer) and not hasattr(transformer, 'end_point'):
                try:
                    # Try to instantiate the transformer class
                    instance = transformer()
                    if hasattr(instance, 'end_point') and instance.end_point:
                        # Register the instance instead of the class for future use
                        self.transformers[name] = instance
                        result.append({"name": name, "transformer": instance})
                except Exception as e:
                    # Log the error but continue processing other transformers
                    log(f"Error instantiating transformer {name}: {e}")
        
        return result
    
    def get_transformers_without_endpoint(self) -> List[Dict[str, Any]]:
        """Get transformers without endpoints"""
        result = []
        
        for name, transformer in self.transformers.items():
            # Check if the transformer is an instance without an endpoint
            if hasattr(transformer, 'end_point') and not transformer.end_point:
                result.append({"name": name, "transformer": transformer})
            # Check if it's a transformer class that needs to be instantiated
            elif callable(transformer) and not hasattr(transformer, 'end_point'):
                try:
                    # Try to instantiate the transformer class
                    instance = transformer()
                    if not hasattr(instance, 'end_point') or not instance.end_point:
                        # For consistency, register the instance instead of the class
                        self.transformers[name] = instance
                        result.append({"name": name, "transformer": instance})
                except Exception as e:
                    # If we can't instantiate, consider it as without endpoint
                    result.append({"name": name, "transformer": transformer})
                    log(f"Error instantiating transformer {name}: {e}")
            # If it's not callable and doesn't have an endpoint, add it as is
            elif not hasattr(transformer, 'end_point'):
                result.append({"name": name, "transformer": transformer})
        
        return result
    
    def remove_transformer(self, name: str) -> bool:
        """Remove a transformer"""
        if name in self.transformers:
            del self.transformers[name]
            return True
        return False
    
    def has_transformer(self, name: str) -> bool:
        """Check if a transformer exists"""
        return name in self.transformers
    
    async def register_transformer_from_config(self, config: Dict[str, Any]) -> bool:
        """Register a transformer from configuration"""
        try:
            if config.get("path"):
                # Dynamically import the module
                module = importlib.import_module(config["path"])
                if module:
                    # Create an instance
                    instance = module.Transformer(config.get("options", {}))
                    if not hasattr(instance, 'name'):
                        log(f"Transformer instance from {config['path']} does not have a name property.")
                        return False
                    
                    self.register_transformer(instance.name, instance)
                    return True
            return False
        except ImportError as error:
            log(f"Failed to import transformer module ({config.get('path')}): {error}")
            return False
        except AttributeError as error:
            log(f"Transformer module ({config.get('path')}) does not have expected attributes: {error}")
            return False
        except Exception as error:
            log(f"Unexpected error loading transformer ({config.get('path')}): {error}")
            return False
    
    async def initialize(self) -> None:
        """Initialize the transformer service"""
        try:
            # Register default transformers
            await self.register_default_transformers_internal()
            
            # Load transformers from configuration
            await self.load_from_config()
        except Exception as error:
            log("TransformerService init error:", error)
            # Log the full traceback for debugging
            import traceback
            log(traceback.format_exc())
            # Continue with partial initialization rather than failing completely
    
    async def register_default_transformers_internal(self) -> None:
        """Register default transformers internally"""
        try:
            # Import transformer module
            from ..transformer import transformers
            
            # Register all transformers
            for transformer_name, transformer_class in transformers.items():
                # Check if the transformer has a static TransformerName property
                if hasattr(transformer_class, 'TransformerName') and isinstance(transformer_class.TransformerName, str):
                    # Register the transformer class with its static name
                    self.register_transformer(transformer_class.TransformerName, transformer_class)
                else:
                    # Try to instantiate the transformer
                    try:
                        # Create an instance
                        transformer_instance = transformer_class()
                        
                        # Determine the name to use for registration
                        if hasattr(transformer_instance, 'name') and transformer_instance.name:
                            # Use the instance's name property
                            self.register_transformer(transformer_instance.name, transformer_instance)
                        else:
                            # Use the transformer_name as fallback
                            self.register_transformer(transformer_name, transformer_instance)
                    except Exception as e:
                        log(f"Error instantiating transformer {transformer_name}: {e}")
                        # Register the class directly if instantiation fails
                        self.register_transformer(transformer_name, transformer_class)
        except Exception as error:
            log("transformer regist error:", error)
    
    async def load_from_config(self) -> None:
        """Load transformers from configuration"""
        transformers_config = self.config_service.get("transformers", [])
        for transformer_config in transformers_config:
            await self.register_transformer_from_config(transformer_config)