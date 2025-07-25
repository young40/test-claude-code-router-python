import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.process_check import get_service_info

def show_status():
    """Show service status"""
    info = get_service_info()
    
    print('\n📊 Claude Code Router Status')
    print('═' * 40)
    
    if info["running"]:
        print('✅ Status: Running')
        print(f'🆔 Process ID: {info["pid"]}')
        print(f'🌐 Port: {info["port"]}')
        print(f'📡 API Endpoint: {info["endpoint"]}')
        print(f'📄 PID File: {info["pid_file"]}')
        print('')
        print('🚀 Ready to use! Run the following commands:')
        print('   python3 cli.py code    # Start coding with Claude')
        print('   python3 cli.py stop   # Stop the service')
    else:
        print('❌ Status: Not Running')
        print('')
        print('💡 To start the service:')
        print('   python3 cli.py start')
    
    print('')