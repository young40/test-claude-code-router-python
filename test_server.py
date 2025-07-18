import asyncio
import sys
sys.path.append('pyllms')

from pyllms.src.services.config import ConfigOptions
from pyllms.src.server import Server

async def test():
    options = ConfigOptions(
        use_json_file=False,
        use_env_file=False,
        use_environment_variables=False,
        initial_config={}
    )
    
    server = Server(options)
    await server.transformer_service.initialize()
    
    print('Transformers with endpoints:')
    for item in server.transformer_service.get_transformers_with_endpoint():
        print(f'- {item["name"]}: {item["transformer"].end_point}')
    
    print('\nAll registered transformers:')
    for name, transformer in server.transformer_service.get_all_transformers().items():
        if hasattr(transformer, 'end_point'):
            endpoint = transformer.end_point
        else:
            # For transformer classes, try to instantiate to check endpoint
            try:
                instance = transformer()
                endpoint = instance.end_point if hasattr(instance, 'end_point') else None
            except:
                endpoint = None
        print(f'- {name}: {endpoint}')

if __name__ == "__main__":
    asyncio.run(test())