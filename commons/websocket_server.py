#!/usr/bin/env python3
"""
单通道WebSocket截图+控制交互服务端
基于单WebSocket通道实现截图数据推送与控制指令交互
"""

import asyncio
import json
import time
import logging
from typing import Optional, Set
from dataclasses import dataclass
from websockets.server import serve, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed
# 导入外部的shared_data单例

# 配置日志
# from commons.helper_shared_data import shared_data








import queue
from threading import Lock

class SharedData:
    """线程安全的共享数据类（单例），存储双向通信队列"""
    _instance = None
    _lock = Lock()  # 单例锁

    def __new__(cls):
        """单例模式：确保所有线程共享同一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # 初始化线程安全队列（核心替换：asyncio.Queue → queue.Queue）
                    cls._instance.ws_to_django_queue = queue.Queue(maxsize=1000)  # WS → Worker 队列
                    cls._instance.django_to_ws_queue = queue.Queue(maxsize=1000)  # Worker → WS 队列
        return cls._instance

    # -------------- WS → Worker 队列操作 --------------
    def put_ws_to_django(self, data):
        """WS线程：向Worker推送数据（非阻塞，队列满则抛异常）"""
        try:
            self.ws_to_django_queue.put_nowait(data)
        except queue.Full:
            print(f"ws_to_django_queue 队列已满，丢弃数据: {data}")

    def get_ws_to_django(self, timeout=None):
        """Worker线程：从WS获取数据（可设置超时，避免永久阻塞）"""
        try:
            return self.ws_to_django_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # -------------- Worker → WS 队列操作 --------------
    def put_django_to_ws(self, data):
        """Worker线程：向WS推送数据"""
        try:
            self.django_to_ws_queue.put_nowait(data)
        except queue.Full:
            print(f"django_to_ws_queue 队列已满，丢弃数据: {data}")

    def get_django_to_ws(self, timeout=None):
        """WS线程：从Worker获取数据"""
        try:
            return self.django_to_ws_queue.get(timeout=timeout)
        except queue.Empty:
            return None

# 全局单例实例（所有线程共享）
shared_data = SharedData()






















logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """服务端配置"""
    host: str = "localhost"
    port: int = 8765
    target_fps: float = 10.0  # 默认10fps
    screenshot_width: int = 360
    screenshot_height: int = 720


class WebSocketServer:
    """WebSocket服务端"""

    def __init__(self, config: ServerConfig = None):
        self.config = config or ServerConfig()
        self.clients: Set[WebSocketServerProtocol] = set()
        self.running = False
        self.frame_interval = 1.0 / self.config.target_fps
        self.django_screenshot_task = None  # Django 消息消费任务

    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """处理客户端连接"""
        client_id = id(websocket)
        logger.info(f"客户端 {client_id} 已连接")
        self.clients.add(websocket)

        try:
            # 仅处理客户端消息（转发给Django），移除截图任务
            async for message in websocket:
                await self._handle_message(websocket, message)

        except ConnectionClosed:
            logger.info(f"客户端 {client_id} 断开连接")
        except Exception as e:
            logger.error(f"处理客户端 {client_id} 时出错: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"客户端 {client_id} 资源已清理")

    async def _handle_message(self, websocket: WebSocketServerProtocol, message):
        """处理客户端消息 - 转发前端配置到ws_to_django_queue"""
        try:
            print('message', message)
            logger.info(f"message", message)
            client_id = id(websocket)
            # 1. 处理二进制消息（前端不应发送，直接忽略）
            if isinstance(message, bytes):
                logger.warning(f"客户端 {client_id} 发送意外二进制消息，长度: {len(message)}")
                await self._send_error(websocket, "请勿发送二进制消息")
                return

            # 2. 解析JSON消息（前端配置/指令）
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                logger.error(f"客户端 {client_id} JSON解析失败: {e}")
                await self._send_error(websocket, "消息格式错误，应为有效JSON")
                return

            # 3. 转发所有前端消息到ws_to_django_queue（由Django处理业务）
            data['from_client_id'] = client_id

            # 写入WS→Django队列（使用外部shared_data的线程安全方法）
            if data.get('name') == 'front':
                logger.debug(f"客户端 {client_id} 消息已转发至Django队列: {data.get('type')}")
                shared_data.put_ws_to_django(data)

            # 4. 向前端返回接收确认（无需等待Django处理结果）
            ack_msg = {
                'type': 'message_received',
                'status': 'success',
                'message': '消息已接收，等待Django处理',
                'timestamp': int(asyncio.get_event_loop().time() * 1000)
            }
            await websocket.send(json.dumps(ack_msg))

        except Exception as e:
            logger.error(f"转发客户端消息失败: {e}")
            await self._send_error(websocket, f"消息转发失败: {str(e)}")

    async def _consume_django_to_ws_queue(self):
        """消费「Django→WS」队列 - 接收截图数据并推送给所有前端"""
        logger.info("启动 Django→WS 截图队列消费任务")
        while self.running:
            try:
                # 从线程安全队列读取消息（超时1s，避免无限阻塞）
                msg = shared_data.get_django_to_ws(timeout=1.0)
                if msg is None:
                    continue  # 无消息时跳过

                msg_type = msg.get('type')
                # 仅处理截图数据消息
                if msg_type == 'screenshot_data':
                    screenshot_bytes = msg.get('data')
                    frame_count = msg.get('frame_count')

                    if screenshot_bytes and self.clients:
                        # 并发推送给所有在线客户端（二进制消息）
                        tasks = [client.send(screenshot_bytes) for client in self.clients if client.open]
                        if tasks:
                            await asyncio.gather(*tasks, return_exceptions=True)
                        logger.debug(f"已推送第 {frame_count} 帧截图给 {len(tasks)} 个客户端")

                elif msg_type == 'group_switch_result':
                    # 转发Django的配置反馈给所有前端
                    await self._broadcast_to_all_clients(msg)

                else:
                    logger.warning(f"收到未知类型的Django消息: {msg_type}")

            except Exception as e:
                logger.error(f"消费Django截图队列失败: {e}")
                await asyncio.sleep(0.5)

    async def _handle_screenshot_ack(self, websocket: WebSocketServerProtocol, data: dict):
        """处理截图确认 - 用于延迟检测"""
        frame_id = data.get('frame_id')
        client_timestamp = data.get('timestamp')
        server_timestamp = int(time.time() * 1000)

        if client_timestamp:
            delay = server_timestamp - client_timestamp
            logger.debug(f"截图延迟: {delay}ms (frame_id: {frame_id})")

            # 可选：根据延迟动态调整帧率
            if delay > 200:  # 延迟超过200ms
                logger.warning(f"检测到高延迟: {delay}ms，考虑降低帧率")

    async def _send_error(self, websocket: WebSocketServerProtocol, message: str):
        """发送错误消息给单个客户端"""
        error_msg = {
            'type': 'error',
            'message': message,
            'timestamp': int(asyncio.get_event_loop().time() * 1000)
        }
        try:
            await websocket.send(json.dumps(error_msg))
        except:
            pass

    async def start(self):
        """启动WebSocket服务器（包含截图队列消费任务）"""
        self.running = True
        # 启动Django截图队列消费任务（后台运行）
        self.django_screenshot_task = asyncio.create_task(self._consume_django_to_ws_queue())
        logger.info(f"启动WebSocket服务器: ws://{self.config.host}:{self.config.port}")
        logger.info(f"目标帧率: {self.config.target_fps} FPS (间隔: {self.frame_interval:.3f}s)")

        async with serve(
                self.handle_client,
                self.config.host,
                self.config.port,
                ping_interval=20,
                ping_timeout=10
        ):
            await asyncio.Future()  # 永久运行

    async def _broadcast_to_all_clients(self, data: dict):
        """向所有在线客户端广播JSON消息"""
        if not self.clients:
            return
        msg = json.dumps(data)
        tasks = [client.send(msg) for client in self.clients if client.open]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def stop(self):
        """停止服务器"""
        self.running = False
        if self.django_screenshot_task:
            self.django_screenshot_task.cancel()
        logger.info("WebSocket服务器已停止（包含截图队列消费任务）")

    async def start_server(self):
        """启动 WebSocket 服务（异步入口）"""
        self.running = True
        logger.info(f"启动WebSocket服务器: ws://{self.config.host}:{self.config.port}")
        async with serve(
            self.handle_client,
            self.config.host,
            self.config.port,
            ping_interval=20,
            ping_timeout=10
        ):
            await asyncio.Future()  # 持续运行


ws_server = WebSocketServer()

if __name__ == '__main__':
    try:
        # 初始化默认配置的服务器
        # ws_server = WebSocketServer()
        # 启动服务器（包含队列消费任务）
        asyncio.run(ws_server.start())
    except KeyboardInterrupt:
        ws_server.stop()
        logger.info("服务器已停止")