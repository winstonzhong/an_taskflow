"""
极简 Mock 设备
只提供框架需要的接口，不模拟真实 ADB 行为
"""

import threading


class MockDevice:
    """
    极简 Mock 设备
    
    只提供框架需要的接口，不模拟真实 ADB 行为
    """
    
    def __init__(self, device_id: str = "mock_device_001"):
        self.device_id = device_id
        self.is_connected = True
        self.is_allocated = False
        self._lock = threading.Lock()
        
    def check_health(self) -> bool:
        """健康检查"""
        return self.is_connected
    
    def allocate(self) -> bool:
        """分配设备"""
        with self._lock:
            if self.is_allocated:
                return False
            self.is_allocated = True
            return True
    
    def release(self):
        """释放设备"""
        with self._lock:
            self.is_allocated = False
    
    def disconnect(self):
        """模拟断开连接"""
        self.is_connected = False
    
    def reconnect(self):
        """模拟重新连接"""
        self.is_connected = True
