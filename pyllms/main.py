#!/usr/bin/env python
"""
PyLLMs 服务入口点
"""
import asyncio
import argparse
import os
from src.server import Server


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="PyLLMs API服务")
    parser.add_argument(
        "--config", 
        type=str, 
        default="./config.json",
        help="配置文件路径 (默认: ./config.json)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=3000,
        help="服务端口 (默认: 3000)"
    )
    parser.add_argument(
        "--host", 
        type=str, 
        default="127.0.0.1",
        help="服务主机地址 (默认: 127.0.0.1)"
    )
    parser.add_argument(
        "--log", 
        action="store_true",
        help="启用日志记录"
    )
    parser.add_argument(
        "--log-file", 
        type=str, 
        default="pyllms.log",
        help="日志文件路径 (默认: pyllms.log)"
    )
    
    return parser.parse_args()


async def main():
    """主函数"""
    args = parse_args()
    
    # 设置环境变量
    if args.log:
        os.environ["LOG"] = "true"
        os.environ["LOG_FILE"] = args.log_file
    
    # 创建服务器配置
    options = {
        "json_path": args.config,
        "initial_config": {
            "PORT": str(args.port),
            "HOST": args.host
        }
    }
    
    # 创建并启动服务器
    server = Server(options)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())