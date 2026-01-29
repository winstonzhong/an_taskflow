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

# 配置日志
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



class SharedData:
    """进程内共享数据容器，用于 Django 业务与 WebSocket 数据交互"""
    def __init__(self):
        # 延迟初始化：在事件循环内创建双向队列（职责分离）
        self.ws_to_django_queue = asyncio.Queue()  # WebSocket → Django（客户端指令、截图状态等）
        self.django_to_ws_queue = asyncio.Queue()  # Django → WebSocket（业务指令、配置更新等）
        self.screenshot_stats = {}  # 截图状态（WebSocket→Django，辅助数据）
        self.lock = asyncio.Lock()  # 异步锁，保证复杂数据结构操作安全

# 移除全局实例，改为工厂函数
_shared_data_instance = None

def get_shared_data():
    """获取共享数据实例（确保与当前事件循环绑定）"""
    global _shared_data_instance
    # 检查当前事件循环，若实例不存在/循环不匹配则重新创建
    current_loop = asyncio.get_running_loop()
    if (_shared_data_instance is None or
        getattr(_shared_data_instance, '_loop', None) != current_loop):
        _shared_data_instance = SharedData()
        _shared_data_instance._loop = current_loop  # 绑定当前循环
    return _shared_data_instance

# 兼容原有代码的全局变量（懒加载）
@property
def shared_data():
    return get_shared_data()


class WebSocketServer:
    """WebSocket服务端"""

    def __init__(self, config: ServerConfig = None):
        self.config = config or ServerConfig()
        self.clients: Set[WebSocketServerProtocol] = set()
        self.running = False
        self.frame_interval = 1.0 / self.config.target_fps
        self.django_msg_task = None  # Django 消息消费任务

    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """处理客户端连接"""
        client_id = id(websocket)
        logger.info(f"客户端 {client_id} 已连接")
        self.clients.add(websocket)

        try:
            # 仅处理客户端消息（转发给Django），移除截图任务
            async for message in websocket:
                # print('msg', message)
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
            shared_data = get_shared_data()
            # 补充客户端标识，方便Django溯源
            forward_data = {
                'from_client_id': client_id,
                'timestamp': asyncio.get_event_loop().time(),
                'data': data
            }
            # 写入WS→Django队列，非阻塞（避免客户端阻塞）
            if data.get('type') == 'selected_scripts':
                logger.debug(f"客户端 {client_id} 消息已转发至Django队列: {data.get('type')}")
                await shared_data.ws_to_django_queue.put(forward_data)

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

    async def _consume_django_screenshot_queue(self):
        """消费「Django→WS」队列 - 接收截图数据并推送给所有前端"""
        logger.info("启动 Django→WS 截图队列消费任务")
        shared_data = get_shared_data()

        while self.running:
            try:
                # 阻塞读取截图消息（超时1s，避免无限等待）
                msg = await asyncio.wait_for(shared_data.django_to_ws_queue.get(), timeout=1.0)
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

                elif msg_type == 'config_feedback':
                    # 转发Django的配置反馈给所有前端
                    await self._broadcast_to_all_clients(msg)

                else:
                    logger.warning(f"收到未知类型的Django消息: {msg_type}")

            except asyncio.TimeoutError:
                pass  # 无消息时跳过
            except Exception as e:
                logger.error(f"消费Django截图队列失败: {e}")
                await asyncio.sleep(0.5)


    async def _handle_control(self, websocket: WebSocketServerProtocol, data: dict):
        action = data.get('action')
        params = data.get('params', {})
        logger.info(f"收到客户端控制指令: {action}, 参数: {params}")

        try:
            # 获取当前循环的共享数据实例
            shared_data = get_shared_data()
            # 向「WebSocket→Django」队列写入指令（供Django业务消费）
            ws_to_django_msg = {
                'type': 'client_control',
                'action': action,
                'params': params,
                'timestamp': time.time(),
                'client_id': id(websocket)
            }
            await shared_data.ws_to_django_queue.put(ws_to_django_msg)  # 写入双向队列的「WS→Django」通道

            # （可选）直接返回客户端即时响应（无需等Django处理）
            instant_result = {
                'type': 'control_ack',
                'status': 'received',
                'action': action,
                'timestamp': int(time.time() * 1000),
                'message': f'指令 "{action}" 已接收，等待Django处理'
            }
            await websocket.send(json.dumps(instant_result))

            # 更新共享状态（供 Django 读取，辅助监控）
            async with shared_data.lock:
                shared_data.screenshot_stats['last_control_action'] = action
                shared_data.screenshot_stats['last_control_time'] = time.time()
                shared_data.screenshot_stats['online_clients'] = len(self.clients)

        except Exception as e:
            logger.error(f"处理控制指令失败: {e}")
            await self._send_error(websocket, f"指令处理失败: {str(e)}")

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
        self.django_screenshot_task = asyncio.create_task(self._consume_django_screenshot_queue())
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

    async def _consume_django_to_ws_queue(self):
        """消费「Django→WebSocket」队列（独立任务，不阻塞客户端连接）"""
        logger.info("启动 Django→WebSocket 队列消费任务")
        while self.running:
            try:
                shared_data = get_shared_data()
                # 阻塞读取（此处可设置超时，避免无限等待）
                msg = await asyncio.wait_for(shared_data.django_to_ws_queue.get(), timeout=1.0)
                msg_type = msg.get('type')

                # 分类型处理 Django 推送的消息
                if msg_type == 'config_update':
                    # 更新服务端配置
                    key = msg.get('key')
                    value = msg.get('value')
                    if key == 'target_fps':
                        self.config.target_fps = max(1, min(30, value))  # 限制帧率范围 1-30
                        self.frame_interval = 1.0 / self.config.target_fps
                        logger.info(f"已更新配置：{key} = {value}（当前帧间隔: {self.frame_interval:.3f}s）")
                        # 向所有在线客户端推送配置更新通知
                        await self._broadcast_to_all_clients({
                            'type': 'config_updated',
                            'key': key,
                            'value': value,
                            'message': f'服务端配置更新：{key} 改为 {value}'
                        })

                elif msg_type == 'control_command':
                    # 执行控制指令（如暂停、恢复截图）
                    action = msg.get('action')
                    message = msg.get('message', '')
                    logger.info(f"执行 Django 控制指令: {action} - {message}")
                    await self._broadcast_to_all_clients({
                        'type': 'server_notice',
                        'action': action,
                        'message': message
                    })

                else:
                    logger.warning(f"收到未知类型的 Django 消息: {msg_type}")

            except asyncio.TimeoutError:
                pass  # 无消息时跳过
            except Exception as e:
                logger.error(f"消费 Django→WebSocket 队列失败: {e}")
                await asyncio.sleep(0.5)

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