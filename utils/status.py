from .process_check import get_service_info

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
        print('   ccr code    # Start coding with Claude')
        print('   ccr stop   # Stop the service')
    else:
        print('❌ Status: Not Running')
        print('')
        print('💡 To start the service:')
        print('   ccr start')
    
    print('')