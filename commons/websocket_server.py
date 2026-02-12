"""
WebSocket 服务器模块
负责与前端建立 WebSocket 连接，并与 Worker 通过队列进行数据交换
"""

import asyncio
import websockets
import json
import threading
import time
import queue  # 添加标准库queue
from typing import Set, Dict, Any

from commons.queue_manager import get_queue_manager


class WebSocketServer:
    """
    WebSocket 服务器
    - 接收前端消息 -> 放入 ws_to_worker 队列
    - 监听 worker_to_ws 队列 -> 推送给前端
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.queue_manager = get_queue_manager()

        # 存储所有连接的客户端 {websocket: client_id}
        self.clients: Dict[websockets.WebSocketServerProtocol, str] = {}
        self.clients_lock = threading.Lock()

        self.server = None
        self.loop = None
        self.thread = None
        self.running = False

        # 使用线程安全的 queue.Queue 替代 asyncio.Queue
        # 用于从同步线程传递数据到异步线程
        self.to_ws_queue = queue.Queue()

    def generate_client_id(self) -> str:
        """生成唯一客户端ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    async def register_client(self, websocket: websockets.WebSocketServerProtocol):
        """注册新客户端"""
        client_id = self.generate_client_id()
        with self.clients_lock:
            self.clients[websocket] = client_id
        print(f"[WebSocket] 客户端 {client_id} 已连接，当前连接数: {len(self.clients)}")
        return client_id

    async def unregister_client(self, websocket: websockets.WebSocketServerProtocol):
        """注销客户端"""
        with self.clients_lock:
            client_id = self.clients.pop(websocket, "unknown")
        print(f"[WebSocket] 客户端 {client_id} 已断开，当前连接数: {len(self.clients)}")

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """
        处理单个客户端连接
        """
        client_id = await self.register_client(websocket)

        try:
            async for message in websocket:
                try:
                    # 解析前端消息
                    data = json.loads(message)
                    print(f"[WebSocket] 收到来自 {client_id} 的消息: {data}")

                    # 添加客户端标识，以便Worker知道回复给谁
                    data["_client_id"] = client_id
                    data["_websocket_id"] = id(websocket)

                    # 放入 ws_to_worker 队列，供 Worker 处理
                    success = self.queue_manager.put_to_worker(data, block=False)
                    if not success:
                        error_msg = {"type": "error", "message": "服务器繁忙，请稍后重试"}
                        await websocket.send(json.dumps(error_msg))

                except json.JSONDecodeError:
                    error_msg = {"type": "error", "message": "无效的JSON格式"}
                    await websocket.send(json.dumps(error_msg))
                except Exception as e:
                    print(f"[WebSocket] 处理消息时出错: {e}")
                    error_msg = {"type": "error", "message": str(e)}
                    await websocket.send(json.dumps(error_msg))

        except websockets.exceptions.ConnectionClosed:
            print(f"[WebSocket] 客户端 {client_id} 连接关闭")
        finally:
            await self.unregister_client(websocket)

    def sync_queue_reader(self):
        """
        同步线程：持续从 worker_to_ws 队列读取数据，放入 self.to_ws_queue
        这是连接同步队列和异步WebSocket的桥梁
        """
        print("[WebSocket] 启动队列读取线程...")

        while self.running:
            try:
                # 从同步队列阻塞读取（带超时以便检查running状态）
                data = self.queue_manager.get_for_ws(block=True, timeout=0.1)

                if data is not None:
                    # 放入线程安全的队列，供异步协程读取
                    self.to_ws_queue.put(data)
                    self.queue_manager.task_done_for_ws()

            except Exception as e:
                if self.running:
                    print(f"[WebSocket] 队列读取错误: {e}")
                time.sleep(0.01)

        print("[WebSocket] 队列读取线程已停止")

    async def broadcast_to_clients(self):
        """
        从线程安全队列读取数据并广播给目标客户端
        """
        print("[WebSocket] 启动消息广播协程...")

        while self.running:
            try:
                # 非阻塞检查队列（使用asyncio的sleep来让出控制权）
                try:
                    data = self.to_ws_queue.get_nowait()

                except queue.Empty:
                    await asyncio.sleep(0.01)  # 使用异步sleep，避免阻塞事件循环
                    continue

                # print('from worker data...', data)

                # 获取目标客户端ID
                target_client_id = data.get("_target_client_id")
                target_websocket_id = data.get("_target_websocket_id")

                # 移除内部字段后再发送给前端
                message = {k: v for k, v in data.items()
                          if not k.startswith("_")}

                send_data = None
                if message.get('type') == 'screenshot_data':
                    send_data = message.get('data')
                else:
                    send_data = json.dumps(message)

                # 发送给指定客户端或广播给所有客户端
                disconnected_clients = []

                with self.clients_lock:
                    clients_snapshot = list(self.clients.items())

                for websocket, client_id in clients_snapshot:
                    should_send = False

                    if target_client_id and client_id == target_client_id:
                        should_send = True
                    elif target_websocket_id and id(websocket) == target_websocket_id:
                        should_send = True
                    elif not target_client_id and not target_websocket_id:
                        should_send = True  # 广播模式

                    if should_send:
                        try:
                            await websocket.send(send_data)
                            print(f"[WebSocket] 消息已发送给 {client_id}")
                        except websockets.exceptions.ConnectionClosed:
                            disconnected_clients.append(websocket)
                        except Exception as e:
                            print(f"[WebSocket] 发送给 {client_id} 失败: {e}")
                            disconnected_clients.append(websocket)

                # 清理已断开的客户端（使用call_soon_threadsafe避免直接调用）
                for ws in disconnected_clients:
                    try:
                        await self.unregister_client(ws)
                    except Exception as e:
                        print(f"[WebSocket] 清理客户端时出错: {e}")

            except Exception as e:
                if self.running:
                    print(f"[WebSocket] 广播错误: {e}")
                    await asyncio.sleep(0.1)  # 出错时短暂休眠

        print("[WebSocket] 消息广播协程已停止")

    async def start_server(self):
        """启动WebSocket服务器"""
        print(f"[WebSocket] 启动服务器于 ws://{self.host}:{self.port}")

        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10
        )

        # 启动广播协程
        broadcast_task = asyncio.create_task(self.broadcast_to_clients())

        try:
            # 保持运行
            await self.server.wait_closed()
        finally:
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass

    def run(self):
        """在新线程中运行WebSocket服务器"""
        self.running = True

        # 启动同步队列读取线程（必须在设置running=True之后）
        queue_thread = threading.Thread(target=self.sync_queue_reader, daemon=True)
        queue_thread.start()

        # 设置并启动事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self.start_server())
        except Exception as e:
            print(f"[WebSocket] 服务器错误: {e}")
        finally:
            self.running = False
            # 取消所有待处理的任务
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()

            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            self.loop.close()

    def start(self):
        """启动WebSocket服务器（非阻塞，在新线程中运行）"""
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return self.thread

    def stop(self):
        """停止WebSocket服务器"""
        print("[WebSocket] 正在停止服务器...")
        self.running = False

        if self.server:
            self.server.close()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        print("[WebSocket] 服务器已停止")


# 便捷启动函数
def start_websocket_server(host: str = "0.0.0.0", port: int = 8765) -> WebSocketServer:
    """启动WebSocket服务器并返回实例"""
    server = WebSocketServer(host=host, port=port)
    server.start()
    return server