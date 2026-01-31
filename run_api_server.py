"""
API 服务器启动脚本
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.server import run_server

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PolyMind MCP API 服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8888, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    print(f"""
╔════════════════════════════════════════════════════════════╗
║           PolyMind MCP API Server v2.0                     ║
╠════════════════════════════════════════════════════════════╣
║  API 地址: http://{args.host}:{args.port:<5}                         ║
║  API 文档: http://{args.host}:{args.port}/api-docs                   ║
║  前端页面: 打开 frontend/index.html                        ║
║                                                            ║
║  新功能:                                                   ║
║    • /trades/large - 大单监控                              ║
║    • /sentiment - 市场情绪指数                             ║
║    • /ws/stats - WebSocket 状态                            ║
║                                                            ║
║  按 Ctrl+C 停止服务器                                      ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    run_server(host=args.host, port=args.port, debug=args.debug)
