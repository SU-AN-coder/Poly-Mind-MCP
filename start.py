"""
PolyMind MCP - 统一启动脚本
启动 MCP API 服务器和前端看板
"""
import os
import sys
import time
import argparse
import threading
import webbrowser
import http.server
import socketserver
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """静默 HTTP 处理器"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)
    
    def log_message(self, format, *args):
        pass  # 禁用请求日志
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


def start_frontend(port: int = 3000):
    """启动前端静态服务器"""
    try:
        with socketserver.TCPServer(("", port), QuietHandler) as httpd:
            httpd.serve_forever()
    except OSError:
        print(f"⚠️  前端端口 {port} 已被占用")


def start_mcp_server(port: int = 8888):
    """启动 MCP API 服务器"""
    subprocess.run([
        sys.executable, "-m", "src.mcp.server",
        "--port", str(port)
    ], cwd=str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="PolyMind MCP 启动器")
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--mcp-port", type=int, default=8888)
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--mcp-only", action="store_true", help="仅启动 MCP 服务器")
    args = parser.parse_args()
    
    print()
    print("=" * 50)
    print("  PolyMind MCP - AI 预测市场分析平台")
    print("=" * 50)
    print()
    
    if args.mcp_only:
        print(f"🚀 MCP 服务器: http://localhost:{args.mcp_port}")
        start_mcp_server(args.mcp_port)
        return
    
    # 启动前端（后台线程）
    frontend_thread = threading.Thread(
        target=start_frontend,
        args=(args.frontend_port,),
        daemon=True
    )
    frontend_thread.start()
    print(f"✅ 前端看板: http://localhost:{args.frontend_port}")
    
    time.sleep(0.5)
    
    # 打开浏览器
    if not args.no_browser:
        webbrowser.open(f"http://localhost:{args.frontend_port}")
    
    print(f"🚀 MCP 服务器: http://localhost:{args.mcp_port}")
    print()
    print("按 Ctrl+C 停止服务")
    print("-" * 50)
    print()
    
    # 启动 MCP 服务器（主线程）
    try:
        start_mcp_server(args.mcp_port)
    except KeyboardInterrupt:
        print("\n✅ 服务已停止")


if __name__ == "__main__":
    main()
