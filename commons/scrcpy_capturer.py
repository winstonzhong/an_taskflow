"""
scrcpy 屏幕推流模块
使用 scrcpy 或 ADB 实现屏幕截图
"""

import subprocess
import threading
import time
import io
import os
import tempfile
import signal
from typing import Optional, Callable, Dict, Any
from pathlib import Path


class ScrcpyCapturer:
    """
    屏幕推流器
    
    注意：当前使用 ADB 截图模式，因为 scrcpy 实时视频流方案
    在录制过程中无法实时提取帧（文件缓存问题）。
    
    后续可以升级为真正的 scrcpy 视频流方案。
    """
    
    def __init__(self,
                 device_serial: Optional[str] = None,
                 capture_interval: float = 0.5,  # 默认 2fps (500ms)
                 quality: int = 80,              # JPEG 质量
                 scale: float = 0.5,             # 截图缩放
                 max_size: int = 720,            # 最大边长（仅参考）
                 bit_rate: int = 2000000,        # 码率（仅参考）
                 max_fps: int = 30):             # 最大帧率（仅参考）
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
        
        # 当前执行的子进程，用于强制终止
        self._current_process: Optional[subprocess.Popen] = None
        self._process_lock = threading.Lock()
        
        # 统计信息
        self.frame_count: int = 0
        self.last_capture_time: float = 0
        self.consecutive_errors: int = 0
        self._status: str = "idle"
    
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
    
    def _capture_frame_adb(self) -> Optional[bytes]:
        """使用 ADB 截图（支持中断）"""
        try:
            cmd = ["adb"]
            if self.device_serial:
                cmd.extend(["-s", self.device_serial])
            cmd.extend(["exec-out", "screencap", "-p"])
            
            # 使用 Popen 以便可以被中断
            with self._process_lock:
                if not self._running:
                    return None
                self._current_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
            
            try:
                # 等待命令完成，超时5秒
                stdout, stderr = self._current_process.communicate(timeout=5)
                
                with self._process_lock:
                    self._current_process = None
                
                if self._current_process and self._current_process.returncode != 0:
                    return None
                
                png_data = stdout
                
                # 压缩处理
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(png_data))
                    
                    # 缩放
                    if self.scale < 1.0:
                        new_size = (int(img.width * self.scale), int(img.height * self.scale))
                        img = img.resize(new_size, Image.Resampling.BILINEAR)
                    
                    # 去除透明通道
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                    
                    # 压缩为 JPEG
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=self.quality, optimize=False)
                    return buffer.getvalue()
                except ImportError:
                    # PIL 不可用，返回原始 PNG
                    return png_data
                except Exception:
                    # 压缩失败，返回原始 PNG
                    return png_data
            except subprocess.TimeoutExpired:
                # 超时，强制终止子进程
                with self._process_lock:
                    if self._current_process:
                        try:
                            self._current_process.kill()
                            self._current_process.wait(timeout=1)
                        except:
                            pass
                        self._current_process = None
                return None
                
        except Exception as e:
            return None
    
    def _capture_loop(self):
        """截图主循环"""
        print(f"[ScrcpyCapturer] 截图循环启动，目标帧率: {1/self.capture_interval:.1f}fps")
        print("[ScrcpyCapturer] 使用 ADB 截图模式")
        
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
                
                # 使用 ADB 截图
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
        
        # 检查设备
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
    
    def stop(self, timeout: float = 3.0):
        """
        停止截图器
        
        Args:
            timeout: 停止超时时间（秒），默认 3 秒
        """
        print(f"[ScrcpyCapturer] 正在停止截图器（超时: {timeout}s）...")
        
        # 第一步：立即终止 adb 子进程，使正在执行的 communicate() 立即返回
        with self._process_lock:
            if self._current_process:
                try:
                    print(f"[ScrcpyCapturer] 终止正在执行的 adb 进程 (PID: {self._current_process.pid})")
                    self._current_process.kill()
                    # 等待进程终止，但使用较短的超时
                    try:
                        self._current_process.wait(timeout=min(0.5, timeout * 0.2))
                    except subprocess.TimeoutExpired:
                        pass  # 继续执行，线程会处理
                except Exception as e:
                    print(f"[ScrcpyCapturer] 终止 adb 进程时出错: {e}")
                finally:
                    self._current_process = None
        
        # 第二步：通知线程停止
        self._running = False
        self._paused = False
        self._set_status("idle")
        
        # 第三步：等待截图线程结束
        if self._capture_thread and self._capture_thread.is_alive():
            print("[ScrcpyCapturer] 等待截图线程结束...")
            # 使用剩余的大部分超时时间等待线程
            thread_timeout = max(0.5, timeout * 0.7)
            self._capture_thread.join(timeout=thread_timeout)
            
            if self._capture_thread.is_alive():
                print(f"[ScrcpyCapturer] 警告: 截图线程在 {thread_timeout}s 内未能停止")
        
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
            "mode": "adb"  # 当前使用 ADB 模式
        }
