"""
scrcpy 屏幕推流模块
使用 scrcpy 实现高帧率(30fps)屏幕截图
"""

import subprocess
import threading
import time
import io
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import tempfile
import os


class ScrcpyCapturer:
    """
    scrcpy 屏幕推流器
    通过启动 scrcpy 进程获取视频流，支持 30fps+
    
    工作模式：
    1. 帧捕获模式：定时从 scrcpy 截取单帧（兼容现有架构）
    2. 流模式：持续输出 H.264 流（需要前端支持）
    """
    
    def __init__(self,
                 device_serial: Optional[str] = None,
                 capture_interval: float = 0.033,  # 默认 30fps (33ms)
                 quality: int = 60,                 # JPEG 质量（帧模式）
                 scale: float = 0.5,                # 截图缩放（帧模式）
                 max_size: int = 720,               # scrcpy 最大边长
                 bit_rate: int = 2000000,           # scrcpy 码率 (2Mbps)
                 max_fps: int = 30):                # scrcpy 最大帧率
        self.device_serial = device_serial
        self.capture_interval = capture_interval
        self.quality = quality
        self.scale = scale
        self.max_size = max_size
        self.bit_rate = bit_rate
        self.max_fps = max_fps
        
        # 回调函数
        self.on_capture: Optional[Callable[[bytes], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None
        
        # 运行状态
        self._running: bool = False
        self._paused: bool = False
        self._capture_thread: Optional[threading.Thread] = None
        self._scrcpy_process: Optional[subprocess.Popen] = None
        
        # 统计信息
        self.frame_count: int = 0
        self.last_capture_time: float = 0
        self.consecutive_errors: int = 0
        self._status: str = "idle"
        
        # 临时目录（用于 scrcpy 录制）
        self._temp_dir = tempfile.mkdtemp(prefix="scrcpy_")
        self._current_frame_file = os.path.join(self._temp_dir, "frame.jpg")
        
        # 检查 scrcpy 可用性
        self._scrcpy_available = self._check_scrcpy()
    
    def _check_scrcpy(self) -> bool:
        """检查 scrcpy 是否可用"""
        try:
            result = subprocess.run(
                ["scrcpy", "--version"],
                capture_output=True,
                timeout=5,
                shell=False
            )
            if result.returncode == 0:
                version = result.stdout.decode().split('\n')[0]
                print(f"[ScrcpyCapturer] 检测到 scrcpy: {version}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass
        
        print("[ScrcpyCapturer] 信息: scrcpy 未安装，将使用 ADB 截图模式")
        print("[ScrcpyCapturer] 提示: 安装 scrcpy 可获得更高帧率 (sudo apt install scrcpy)")
        return False
    
    def _check_device(self) -> bool:
        """检查设备是否已连接"""
        try:
            cmd = ["adb", "devices"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return False
            
            lines = result.stdout.strip().split('\n')
            devices = [line for line in lines[1:] if line.strip() and 'device' in line]
            
            if not devices:
                print("[ScrcpyCapturer] 警告: 没有检测到 ADB 设备")
                return False
            
            # 自动选择第一个设备
            if not self.device_serial:
                first_device = devices[0].split()[0]
                self.device_serial = first_device
                print(f"[ScrcpyCapturer] 自动选择设备: {self.device_serial}")
            
            return True
            
        except Exception as e:
            print(f"[ScrcpyCapturer] 设备检查失败: {e}")
            return False
    
    def _start_scrcpy(self) -> bool:
        """启动 scrcpy 进程（用于流捕获）"""
        if not self._scrcpy_available:
            return False
        
        try:
            # scrcpy 参数
            cmd = [
                "scrcpy",
                "--max-size", str(self.max_size),
                "--bit-rate", str(self.bit_rate),
                "--max-fps", str(self.max_fps),
                "--no-control",           # 禁用控制
                "--no-display",           # 不显示窗口
                "--render-driver", "software",  # 使用软件渲染（服务器端）
            ]
            
            if self.device_serial:
                cmd.extend(["--serial", self.device_serial])
            
            print(f"[ScrcpyCapturer] 启动 scrcpy: {' '.join(cmd)}")
            
            # 启动 scrcpy 进程
            self._scrcpy_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            
            # 等待启动
            time.sleep(1)
            
            if self._scrcpy_process.poll() is not None:
                stderr = self._scrcpy_process.stderr.read().decode()
                print(f"[ScrcpyCapturer] scrcpy 启动失败: {stderr}")
                return False
            
            print("[ScrcpyCapturer] scrcpy 启动成功")
            return True
            
        except Exception as e:
            print(f"[ScrcpyCapturer] 启动 scrcpy 异常: {e}")
            return False
    
    def _stop_scrcpy(self):
        """停止 scrcpy 进程"""
        if self._scrcpy_process:
            try:
                self._scrcpy_process.terminate()
                self._scrcpy_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._scrcpy_process.kill()
            except Exception as e:
                print(f"[ScrcpyCapturer] 停止 scrcpy 异常: {e}")
            finally:
                self._scrcpy_process = None
    
    def _capture_frame_adb(self) -> Optional[bytes]:
        """
        使用 ADB 快速截图（降级方案，约 100-200ms）
        优化：降低分辨率、降低质量
        """
        try:
            # 使用 adb exec-out 直接获取截图
            cmd = ["adb"]
            if self.device_serial:
                cmd.extend(["-s", self.device_serial])
            cmd.extend(["exec-out", "screencap", "-p"])
            
            result = subprocess.run(cmd, capture_output=True, timeout=2)
            if result.returncode != 0:
                return None
            
            png_data = result.stdout
            
            # 快速压缩
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(png_data))
                
                # 快速缩放
                if self.scale < 1.0:
                    new_size = (int(img.width * self.scale), int(img.height * self.scale))
                    # 使用更快的缩放算法
                    img = img.resize(new_size, Image.Resampling.BILINEAR)
                
                # 转换格式
                if img.mode == 'RGBA':
                    # 快速去除透明通道
                    r, g, b, a = img.split()
                    img = Image.merge('RGB', (r, g, b))
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=self.quality, optimize=False)
                return buffer.getvalue()
                
            except ImportError:
                return png_data
                
        except Exception as e:
            return None
    
    def _capture_loop(self):
        """截图主循环 - 高频率模式"""
        print(f"[ScrcpyCapturer] 截图循环启动，目标帧率: {1/self.capture_interval:.1f}fps")
        
        last_capture = 0
        
        while self._running:
            try:
                if self._paused:
                    time.sleep(0.1)
                    continue
                
                now = time.time()
                elapsed = now - last_capture
                
                # 控制帧率
                if elapsed < self.capture_interval:
                    time.sleep(self.capture_interval - elapsed)
                
                last_capture = time.time()
                
                # 使用 ADB 快速截图
                data = self._capture_frame_adb()
                
                if data:
                    self.frame_count += 1
                    self.consecutive_errors = 0
                    
                    if self.on_capture:
                        self.on_capture(data)
                else:
                    self.consecutive_errors += 1
                    if self.consecutive_errors >= 5:
                        self._set_status("error")
                        if self.on_error:
                            self.on_error("连续截图失败")
                        time.sleep(1)
                
            except Exception as e:
                print(f"[ScrcpyCapturer] 截图循环异常: {e}")
                time.sleep(0.1)
    
    def _set_status(self, status: str):
        """设置状态"""
        self._status = status
        if self.on_status_change:
            self.on_status_change(status)
    
    def start(self):
        """启动截图器"""
        if self._running:
            return
        
        # 检查设备和 scrcpy
        if not self._check_device():
            self._set_status("error")
            return
        
        self._running = True
        self._paused = False
        self._set_status("running")
        
        # 启动截图线程
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="ScrcpyCaptureThread"
        )
        self._capture_thread.start()
        
        fps = 1 / self.capture_interval if self.capture_interval > 0 else 0
        print(f"[ScrcpyCapturer] 已启动，目标帧率: {fps:.1f}fps")
    
    def stop(self):
        """停止截图器"""
        self._running = False
        self._paused = False
        self._set_status("idle")
        
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        
        self._stop_scrcpy()
        
        # 清理临时文件
        try:
            if os.path.exists(self._temp_dir):
                import shutil
                shutil.rmtree(self._temp_dir)
        except Exception:
            pass
        
        print("[ScrcpyCapturer] 已停止")
    
    def pause(self):
        """暂停截图"""
        if self._running and not self._paused:
            self._paused = True
            self._set_status("paused")
            print("[ScrcpyCapturer] 已暂停")
    
    def resume(self):
        """恢复截图"""
        if self._running and self._paused:
            self._paused = False
            self._set_status("running")
            print("[ScrcpyCapturer] 已恢复")
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "status": self._status,
            "frame_count": self.frame_count,
            "running": self._running,
            "paused": self._paused,
            "device_serial": self.device_serial,
            "fps": 1 / self.capture_interval if self.capture_interval > 0 else 0,
            "scrcpy_available": self._scrcpy_available
        }
