"""
屏幕截图模块
支持多种截图方式：ADB、Mock（向后兼容）
"""

import subprocess
import io
import time
import threading
from typing import Optional, Callable, Dict, Any
from enum import Enum


class CaptureMethod(Enum):
    """截图方式枚举"""
    MOCK = "mock"           # 模拟截图（向后兼容）
    ADB = "adb"             # ADB 截图
    AUTO = "auto"           # 自动选择


class ScreenCapturer:
    """
    屏幕截图器
    负责获取 Android 设备的真实屏幕截图
    """
    
    def __init__(self, 
                 device_serial: Optional[str] = None,
                 method: CaptureMethod = CaptureMethod.AUTO,
                 capture_interval: float = 1.0,    # 默认 1fps
                 quality: int = 80,                 # JPEG质量
                 scale: float = 1.0,                # 截图缩放比例
                 max_retries: int = 3,              # 最大重试次数
                 retry_interval: float = 5.0):      # 重试间隔（秒）
        self.device_serial = device_serial
        self.method = method
        self.capture_interval = capture_interval
        self.quality = quality
        self.scale = scale
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        
        self._current_method: CaptureMethod = method
        self._adb_available: bool = False
        self._mock_generator = None
        
        # 回调函数：当有新截图时调用
        self.on_capture: Optional[Callable[[bytes], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None
        
        # 运行状态
        self._running: bool = False
        self._paused: bool = False
        self._capture_thread: Optional[threading.Thread] = None
        
        # 统计信息
        self.frame_count: int = 0
        self.last_capture_time: float = 0
        self.consecutive_errors: int = 0
        
        # 状态：idle, running, paused, error
        self._status: str = "idle"
        
        self._init_method()
    
    def _init_method(self):
        """初始化截图方式"""
        if self.method == CaptureMethod.AUTO:
            if self._check_adb():
                self._current_method = CaptureMethod.ADB
            else:
                self._current_method = CaptureMethod.MOCK
                self._init_mock()
        elif self.method == CaptureMethod.ADB:
            self._adb_available = self._check_adb()
            if not self._adb_available:
                print("[ScreenCapturer] 警告: ADB 不可用，将使用 Mock 模式")
                self._current_method = CaptureMethod.MOCK
                self._init_mock()
        elif self.method == CaptureMethod.MOCK:
            self._init_mock()
        
        print(f"[ScreenCapturer] 使用截图方式: {self._current_method.value}")
    
    def _check_adb(self) -> bool:
        """检查 ADB 是否可用"""
        try:
            cmd = ["adb", "devices"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return False
            
            lines = result.stdout.strip().split('\n')
            devices = [line for line in lines[1:] if line.strip() and 'device' in line]
            
            if not devices:
                print("[ScreenCapturer] 警告: 没有检测到 ADB 设备")
                return False
            
            if self.device_serial:
                device_exists = any(self.device_serial in line for line in devices)
                if not device_exists:
                    print(f"[ScreenCapturer] 警告: 未找到指定设备 {self.device_serial}")
                    return False
            else:
                # 自动选择第一个设备
                first_device = devices[0].split()[0]
                self.device_serial = first_device
                print(f"[ScreenCapturer] 自动选择设备: {self.device_serial}")
            
            print(f"[ScreenCapturer] 检测到 ADB 设备: {devices}")
            return True
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"[ScreenCapturer] ADB 检查失败: {e}")
            return False
    
    def _init_mock(self):
        """初始化模拟截图器（向后兼容）"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            self._mock_generator = MockScreenshotGenerator()
            print("[ScreenCapturer] 已初始化 Mock 截图器")
        except ImportError:
            print("[ScreenCapturer] 警告: PIL 不可用，Mock 模式将无法工作")
    
    def _capture_adb(self) -> Optional[bytes]:
        """
        使用 ADB 截图
        优化版：使用 exec-out 直接输出到 stdout，避免文件 IO
        """
        try:
            # 优化版：使用 exec-out 直接获取截图数据
            cmd = ["adb"]
            if self.device_serial:
                cmd.extend(["-s", self.device_serial])
            cmd.extend(["exec-out", "screencap", "-p"])
            
            result = subprocess.run(cmd, capture_output=True, timeout=3)
            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "截图命令失败"
                raise RuntimeError(f"截图失败: {error_msg}")
            
            png_data = result.stdout
            
            # 如果不需要缩放且质量设置为100，直接返回PNG（更快）
            if self.scale >= 1.0 and self.quality >= 95:
                return png_data
            
            # PIL 处理：缩放 + 压缩
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(png_data))
                
                # 缩放图像（如果需要）
                if self.scale < 1.0:
                    new_size = (int(img.width * self.scale), int(img.height * self.scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # 处理透明通道
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=self.quality, optimize=True)
                return buffer.getvalue()
                
            except ImportError:
                return png_data
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("截图超时")
        except Exception as e:
            raise RuntimeError(f"截图异常: {e}")
    
    def _capture_mock(self) -> Optional[bytes]:
        """使用 Mock 截图（向后兼容）"""
        if self._mock_generator:
            return self._mock_generator.generate()
        return None
    
    def capture(self) -> Optional[bytes]:
        """执行一次截图"""
        start_time = time.time()
        
        try:
            if self._current_method == CaptureMethod.ADB:
                data = self._capture_adb()
            else:
                data = self._capture_mock()
            
            if data:
                self.frame_count += 1
                self.last_capture_time = time.time() - start_time
                self.consecutive_errors = 0  # 重置错误计数
            
            return data
            
        except Exception as e:
            self.consecutive_errors += 1
            error_msg = str(e)
            print(f"[ScreenCapturer] 截图失败 ({self.consecutive_errors}/{self.max_retries}): {error_msg}")
            
            # 触发错误回调
            if self.on_error:
                self.on_error(error_msg)
            
            # 检查是否需要重连
            if self.consecutive_errors >= self.max_retries:
                self._set_status("error")
                if self._current_method == CaptureMethod.ADB:
                    print("[ScreenCapturer] 尝试重新检测 ADB 连接...")
                    if not self._check_adb():
                        print("[ScreenCapturer] ADB 重连失败，切换到 Mock 模式")
                        self._current_method = CaptureMethod.MOCK
                        self._init_mock()
                    else:
                        self.consecutive_errors = 0
            
            return None
    
    def start(self):
        """启动定时截图线程"""
        if self._running:
            return
        
        self._running = True
        self._paused = False
        self._set_status("running")
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="ScreenCaptureThread"
        )
        self._capture_thread.start()
        method_name = "ADB" if self._current_method == CaptureMethod.ADB else "Mock"
        print(f"[ScreenCapturer] 截图线程已启动，模式: {method_name}, 帧率: {1/self.capture_interval:.1f}fps")
    
    def stop(self):
        """停止截图线程"""
        self._running = False
        self._paused = False
        self._set_status("idle")
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        print("[ScreenCapturer] 截图线程已停止")
    
    def pause(self):
        """暂停截图"""
        if self._running and not self._paused:
            self._paused = True
            self._set_status("paused")
            print("[ScreenCapturer] 截图已暂停")
    
    def resume(self):
        """恢复截图"""
        if self._running and self._paused:
            self._paused = False
            self._set_status("running")
            print("[ScreenCapturer] 截图已恢复")
    
    def _set_status(self, status: str):
        """设置状态并触发回调"""
        self._status = status
        if self.on_status_change:
            self.on_status_change(status)
    
    def _capture_loop(self):
        """截图主循环"""
        while self._running:
            try:
                if not self._paused:
                    data = self.capture()
                    
                    if data and self.on_capture:
                        self.on_capture(data)
                
                # 控制截图频率
                time.sleep(self.capture_interval)
                
            except Exception as e:
                print(f"[ScreenCapturer] 截图循环异常: {e}")
                time.sleep(self.retry_interval)  # 出错后等待再试
    
    def get_status(self) -> Dict[str, Any]:
        """获取截图器状态"""
        return {
            "status": self._status,
            "method": self._current_method.value,
            "frame_count": self.frame_count,
            "last_capture_time_ms": self.last_capture_time * 1000,
            "running": self._running,
            "paused": self._paused,
            "device_serial": self.device_serial,
            "fps": 1/self.capture_interval if self.capture_interval > 0 else 0,
            "scale": self.scale,
            "quality": self.quality
        }


class MockScreenshotGenerator:
    """模拟截图生成器（向后兼容）"""
    
    def __init__(self, width: int = 360, height: int = 720):
        self.width = width
        self.height = height
        self.frame_count = 0
    
    def generate(self) -> Optional[bytes]:
        """生成模拟截图（JPEG格式）"""
        try:
            from PIL import Image, ImageDraw
            import io
            
            img = Image.new('RGB', (self.width, self.height), color='#1a1a2e')
            draw = ImageDraw.Draw(img)
            
            self.frame_count += 1
            
            # 绘制背景
            for y in range(0, self.height, 4):
                color_val = int(30 + (y / self.height) * 50)
                draw.line([(0, y), (self.width, y)], fill=(color_val, color_val, color_val + 30))
            
            # 绘制状态栏
            draw.rectangle([0, 0, self.width, 24], fill='#000000')
            draw.text((10, 4), "9:41", fill='#ffffff')
            
            # 绘制应用网格
            app_colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57', '#ff9ff3', '#54a0ff', '#48dbfb']
            icon_size = 48
            gap = 20
            cols = 4
            start_y = 60
            
            for i in range(16):
                row = i // cols
                col = i % cols
                x = 20 + col * (icon_size + gap)
                y = start_y + row * (icon_size + gap + 20)
                color = app_colors[i % len(app_colors)]
                draw.rounded_rectangle([x, y, x + icon_size, y + icon_size], radius=10, fill=color)
            
            # 绘制底部Dock
            dock_y = self.height - 100
            draw.rounded_rectangle([20, dock_y, self.width - 20, dock_y + 70], radius=20, fill='#ffffff20')
            for i in range(4):
                x = 40 + i * (icon_size + 20)
                color = app_colors[i % len(app_colors)]
                draw.rounded_rectangle([x, dock_y + 11, x + icon_size, dock_y + 11 + icon_size], radius=10, fill=color)
            
            # 绘制帧率信息
            draw.text((10, self.height - 30), f"Frame: {self.frame_count} | MOCK MODE", fill='#ffffff80')
            
            # 绘制扫描线效果
            scan_y = (self.frame_count * 3) % self.height
            draw.line([(0, scan_y), (self.width, scan_y)], fill='#00d4ff40', width=2)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=80)
            return buffer.getvalue()
            
        except ImportError:
            return None
        except Exception as e:
            print(f"[MockScreenshotGenerator] 生成失败: {e}")
            return None
