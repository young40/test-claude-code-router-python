import asyncio
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict
import threading
import time

class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, server_instance, *args, **kwargs):
        self.server_instance = server_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        print(f"\n📥 GET Request received: {self.path}")
        print(f"📋 Headers: {self.headers}")
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {"status": "running", "message": "Claude Code Router is running"}
        self.wfile.write(json.dumps(response).encode())
        
        print(f"📤 Response: {json.dumps(response)}")
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        print(f"\n📥 POST Request received: {self.path}")
        print(f"📋 Headers: {self.headers}")
        try:
            decoded_data = json.loads(post_data.decode('utf-8'))
            print(f"📦 Request Body: {json.dumps(decoded_data, indent=2)}")
        except:
            print(f"📦 Request Body (raw): {post_data}")
        
        # Process hooks
        for hook_type, handler in self.server_instance.hooks:
            if hook_type == "pre_handler":
                try:
                    if asyncio.iscoroutinefunction(handler):
                        # For async handlers, we'd need to run them properly
                        pass
                    else:
                        handler(self, None)
                except Exception as e:
                    print(f"❌ Hook error: {e}")
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {"status": "processed"}
        self.wfile.write(json.dumps(response).encode())
        
        print(f"📤 Response: {json.dumps(response)}")
    
    def log_message(self, format, *args):
        # Custom logging
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

class Server:
    """Python equivalent of @musistudio/llms Server"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.hooks = []
        self.httpd = None
    
    def add_hook(self, hook_type: str, handler):
        """Add a hook handler"""
        self.hooks.append((hook_type, handler))
    
    def start(self):
        """Start the server"""
        host = self.config.get('HOST', '127.0.0.1')
        port = self.config.get('PORT', 3456)
        
        print(f"🚀 Server starting on {host}:{port}")
        
        # Create handler with server instance
        handler = lambda *args, **kwargs: RequestHandler(self, *args, **kwargs)
        
        try:
            self.httpd = HTTPServer((host, port), handler)
            print(f"✅ Server is running on http://{host}:{port}")
            print("📝 Logs will appear here...")
            print("🛑 Press Ctrl+C to stop the server")
            
            # This will block and keep the server running
            self.httpd.serve_forever()
            
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            self.stop()
        except Exception as e:
            print(f"❌ Server error: {e}")
    
    def stop(self):
        """Stop the server"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("🔴 Server stopped")

def create_server(config: Dict[str, Any]) -> Server:
    """Create and return a server instance"""
    return Server(config)