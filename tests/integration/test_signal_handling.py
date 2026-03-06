"""
信号处理测试 - 确保 python main.py Ctrl+C 能完全退出

这些测试会实际启动子进程，验证信号处理逻辑
"""

import os
import sys
import time
import signal
import socket
import subprocess
import tempfile
import threading

import pytest
import psutil


@pytest.mark.signal
@pytest.mark.slow
class TestSignalHandling:
    """
    测试 Ctrl+C 信号处理
    
    这些测试启动真实子进程来模拟 main.py 的行为
    """
    
    def test_sigint_graceful_shutdown(self, tmp_path):
        """
        测试 Ctrl+C 优雅关闭
        
        场景：
        - 启动模拟 main.py（包含多个子进程）
        - 发送 SIGINT (Ctrl+C)
        - 期望所有子进程被清理
        """
        # 创建模拟 main.py 脚本
        main_script = tmp_path / "mock_main.py"
        main_script.write_text('''
import os
import sys
import time
import signal
import multiprocessing

def worker_process(worker_id):
    """模拟 Worker 进程"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # 子进程忽略 SIGINT
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    while True:
        time.sleep(0.1)

if __name__ == "__main__":
    # 启动多个子进程（模拟 Worker）
    processes = []
    for i in range(3):
        p = multiprocessing.Process(target=worker_process, args=(i,))
        p.start()
        processes.append(p)
    
    # 写入 PID 文件
    with open("pids.txt", "w") as f:
        f.write(f"{os.getpid()}\\n")
        for p in processes:
            f.write(f"{p.pid}\\n")
    
    # 信号处理
    def handler(signum, frame):
        print(f"[Main] 收到信号 {signum}，正在关闭...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        # 等待子进程结束
        for p in processes:
            p.join(timeout=3)
            if p.is_alive():
                p.kill()
                p.join()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    
    # 保持运行
    while True:
        time.sleep(1)
''')
        
        # 启动进程
        proc = subprocess.Popen(
            [sys.executable, str(main_script)],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待 PID 文件写入
        pid_file = tmp_path / "pids.txt"
        for _ in range(50):
            if pid_file.exists():
                break
            time.sleep(0.1)
        
        assert pid_file.exists(), "PID 文件未创建"
        
        # 读取 PID
        lines = pid_file.read_text().strip().split('\n')
        main_pid = int(lines[0])
        child_pids = [int(pid) for pid in lines[1:] if pid]
        
        print(f"主进程 PID: {main_pid}")
        print(f"子进程 PIDs: {child_pids}")
        
        # 验证子进程存在
        for pid in child_pids:
            assert psutil.pid_exists(pid), f"子进程 {pid} 不存在"
        
        # 发送 SIGINT (Ctrl+C)
        os.kill(main_pid, signal.SIGINT)
        
        # 等待进程退出
        try:
            stdout, stderr = proc.communicate(timeout=10)
            print(f"stdout: {stdout.decode()}")
        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("进程未在 10 秒内退出")
        
        # 验证返回码
        assert proc.returncode == 0, f"进程返回码非 0: {proc.returncode}"
        
        # 验证所有子进程已终止
        time.sleep(0.5)
        for pid in child_pids:
            assert not psutil.pid_exists(pid), f"子进程 {pid} 仍然存在"
    
    def test_signal_handler_with_stopping_flag(self, tmp_path):
        """
        测试信号处理的 _stopping 标志防止重复调用
        
        场景：
        - 主进程收到 SIGINT
        - 设置 _stopping = True
        - 再次收到 SIGINT（用户多次按 Ctrl+C）
        - 期望：第二次被忽略，不会重复执行 stop()
        """
        main_script = tmp_path / "stopping_flag_test.py"
        main_script.write_text('''
import os
import sys
import time
import signal
import threading

# 全局标志
stop_count = 0
stopping = False

def safe_stop():
    """模拟停止函数"""
    global stop_count
    stop_count += 1
    print(f"[Main] stop() 被调用 #{stop_count}")
    time.sleep(0.5)  # 模拟停止耗时

def handler(signum, frame):
    """信号处理函数"""
    global stopping
    
    print(f"[Main] 收到信号 {signum}")
    
    # 检查是否已经在停止过程中
    if stopping:
        print("[Main] 停止已在进行中，跳过...")
        return
    stopping = True
    
    # 启动后台线程执行停止
    stop_thread = threading.Thread(target=safe_stop)
    stop_thread.daemon = True
    stop_thread.start()
    
    # 等待停止完成
    stop_thread.join(timeout=2)
    
    print(f"[Main] 退出，stop() 被调用次数: {stop_count}")
    sys.exit(0)

# 写入 PID
with open("flag_test_pid.txt", "w") as f:
    f.write(str(os.getpid()))

signal.signal(signal.SIGINT, handler)

while True:
    time.sleep(1)
''')
        
        proc = subprocess.Popen(
            [sys.executable, str(main_script)],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待 PID 文件
        pid_file = tmp_path / "flag_test_pid.txt"
        for _ in range(50):
            if pid_file.exists():
                break
            time.sleep(0.1)
        
        main_pid = int(pid_file.read_text().strip())
        
        # 快速发送两次 SIGINT（模拟用户多次按 Ctrl+C）
        os.kill(main_pid, signal.SIGINT)
        time.sleep(0.1)  # 稍微等待一下
        os.kill(main_pid, signal.SIGINT)
        
        # 等待退出
        stdout, stderr = proc.communicate(timeout=10)
        
        output = stdout.decode()
        print(f"output: {output}")
        
        # 验证 stop() 只被调用一次
        assert "停止已在进行中，跳过" in output, "第二次 SIGINT 应该被忽略"
        assert output.count("stop() 被调用 #1") == 1, "stop() 应该只被调用一次"
        assert "stop() 被调用 #2" not in output, "stop() 不应该被调用两次"
    
    def test_no_self_join_error(self, tmp_path):
        """
        测试不会尝试 join 当前线程
        
        场景：
        - 信号处理函数在主线程中执行
        - 尝试 stop() 时检查监控线程
        - 监控线程就是当前线程
        - 期望：不会尝试 join 自己，不会抛出 RuntimeError
        """
        main_script = tmp_path / "no_self_join_test.py"
        main_script.write_text('''
import os
import sys
import time
import signal
import threading

monitor_thread = None
stop_executed = False
join_error = False

def stop_services():
    """停止服务"""
    global stop_executed, join_error
    
    try:
        current_thread = threading.current_thread()
        
        # 检查监控线程是否是当前线程
        if (monitor_thread is not None and 
            monitor_thread is not current_thread and 
            monitor_thread.is_alive()):
            monitor_thread.join(timeout=1)
        elif monitor_thread is current_thread:
            print("[Main] 监控线程就是当前线程，跳过 join")
        
        stop_executed = True
        print("[Main] stop_services() 成功执行")
    except RuntimeError as e:
        join_error = True
        print(f"[Main] RuntimeError: {e}")

def handler(signum, frame):
    """信号处理"""
    print(f"[Main] 收到信号 {signum}")
    
    stop_thread = threading.Thread(target=stop_services)
    stop_thread.daemon = True
    stop_thread.start()
    stop_thread.join(timeout=3)
    
    if join_error:
        sys.exit(1)  # 出错
    else:
        sys.exit(0)  # 正常退出

def monitor():
    """监控线程"""
    global monitor_thread
    monitor_thread = threading.current_thread()
    
    with open("monitor_pid.txt", "w") as f:
        f.write(f"{os.getpid()}\\n{monitor_thread.ident}\\n")
    
    print("[Monitor] 监控线程启动")
    
    while True:
        time.sleep(0.5)

# 启动监控线程
m = threading.Thread(target=monitor, name="monitor")
m.daemon = True
m.start()

# 等待监控线程设置好
while monitor_thread is None:
    time.sleep(0.1)

signal.signal(signal.SIGINT, handler)

while True:
    time.sleep(1)
''')
        
        proc = subprocess.Popen(
            [sys.executable, str(main_script)],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待 PID 文件
        pid_file = tmp_path / "monitor_pid.txt"
        for _ in range(50):
            if pid_file.exists():
                break
            time.sleep(0.1)
        
        lines = pid_file.read_text().strip().split('\n')
        main_pid = int(lines[0])
        
        # 等待一下让信号处理设置好
        time.sleep(0.5)
        
        # 发送 SIGINT（这时监控线程应该已经在运行）
        os.kill(main_pid, signal.SIGINT)
        
        stdout, stderr = proc.communicate(timeout=10)
        
        print(f"stdout: {stdout.decode()}")
        print(f"stderr: {stderr.decode()}")
        
        # 验证没有 RuntimeError
        assert "RuntimeError" not in stdout.decode(), "不应该出现 RuntimeError"
        assert "cannot join current thread" not in stdout.decode(), "不应该尝试 join 当前线程"
        assert proc.returncode == 0, f"返回码应该是 0，实际是 {proc.returncode}"
    
    def test_force_kill_on_timeout(self, tmp_path):
        """
        测试优雅关闭超时后的强制终止
        
        场景：子进程不响应 SIGTERM，需要 SIGKILL
        """
        main_script = tmp_path / "stubborn_main.py"
        main_script.write_text('''
import os
import sys
import time
import signal
import multiprocessing

def stubborn_worker():
    """忽略 SIGTERM 的顽固进程"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)  # 忽略 SIGTERM
    while True:
        time.sleep(0.1)

if __name__ == "__main__":
    p = multiprocessing.Process(target=stubborn_worker)
    p.start()
    
    with open("stubborn_pid.txt", "w") as f:
        f.write(f"{os.getpid()}\\n{p.pid}\\n")
    
    def handler(signum, frame):
        print(f"[Main] 收到信号 {signum}")
        p.terminate()
        p.join(timeout=1)
        if p.is_alive():
            print("[Main] 子进程不响应 SIGTERM，使用 SIGKILL")
            p.kill()
            p.join()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handler)
    
    while True:
        time.sleep(1)
''')
        
        proc = subprocess.Popen(
            [sys.executable, str(main_script)],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待 PID 文件
        pid_file = tmp_path / "stubborn_pid.txt"
        for _ in range(50):
            if pid_file.exists():
                break
            time.sleep(0.1)
        
        lines = pid_file.read_text().strip().split('\n')
        main_pid = int(lines[0])
        child_pid = int(lines[1])
        
        # 验证子进程存在
        assert psutil.pid_exists(child_pid)
        
        # 发送 SIGINT
        os.kill(main_pid, signal.SIGINT)
        
        # 等待退出
        stdout, stderr = proc.communicate(timeout=10)
        
        print(f"stdout: {stdout.decode()}")
        
        # 验证 SIGKILL 被使用
        assert "SIGKILL" in stdout.decode() or proc.returncode == 0
        
        # 验证子进程已终止
        assert not psutil.pid_exists(child_pid)
    
    def test_no_orphan_processes(self, tmp_path):
        """
        测试无孤儿进程残留
        
        模拟多层进程结构，验证全部清理
        """
        main_script = tmp_path / "nested_main.py"
        main_script.write_text('''
import os
import sys
import time
import signal
import multiprocessing

def grandchild():
    """孙进程"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    while True:
        time.sleep(0.1)

def child():
    """子进程，再创建孙进程"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    gc = multiprocessing.Process(target=grandchild)
    gc.start()
    gc.join()

if __name__ == "__main__":
    p = multiprocessing.Process(target=child)
    p.start()
    
    # 给时间让孙进程创建
    time.sleep(0.5)
    
    with open("nested_pids.txt", "w") as f:
        f.write(f"{os.getpid()}\\n{p.pid}\\n")
    
    def handler(signum, frame):
        # 使用 psutil 递归杀死所有子进程
        import psutil
        parent = psutil.Process(os.getpid())
        children = parent.children(recursive=True)
        for child in children:
            child.terminate()
        gone, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            child.kill()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handler)
    
    while True:
        time.sleep(1)
''')
        
        proc = subprocess.Popen(
            [sys.executable, str(main_script)],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 读取 PID
        pid_file = tmp_path / "nested_pids.txt"
        for _ in range(50):
            if pid_file.exists():
                break
            time.sleep(0.1)
        
        lines = pid_file.read_text().strip().split('\n')
        main_pid = int(lines[0])
        child_pid = int(lines[1])
        
        # 等待孙进程创建
        time.sleep(1)
        
        # 获取所有后代进程
        parent = psutil.Process(main_pid)
        descendants_before = parent.children(recursive=True)
        print(f"关闭前的后代进程: {[p.pid for p in descendants_before]}")
        
        # 发送 SIGINT
        os.kill(main_pid, signal.SIGINT)
        
        # 等待退出
        proc.communicate(timeout=10)
        
        # 验证无残留进程
        for p in descendants_before:
            assert not psutil.pid_exists(p.pid), f"进程 {p.pid} 残留"
    
    def test_port_release_on_exit(self, tmp_path):
        """
        测试端口在退出后被释放
        """
        main_script = tmp_path / "port_holder.py"
        main_script.write_text('''
import os
import sys
import time
import signal
import socket

# 占用一个端口
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", 0))  # 随机端口
port = sock.getsockname()[1]
sock.listen(5)

with open("port.txt", "w") as f:
    f.write(f"{os.getpid()}\\n{port}\\n")

def handler(signum, frame):
    print("[Main] 关闭 socket")
    sock.close()
    sys.exit(0)

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

while True:
    time.sleep(1)
''')
        
        proc = subprocess.Popen(
            [sys.executable, str(main_script)],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 读取端口
        port_file = tmp_path / "port.txt"
        for _ in range(50):
            if port_file.exists():
                break
            time.sleep(0.1)
        
        lines = port_file.read_text().strip().split('\n')
        pid = int(lines[0])
        port = int(lines[1])
        
        # 验证端口被占用
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = test_sock.connect_ex(("127.0.0.1", port))
        test_sock.close()
        assert result == 0, "端口未被占用（测试设置失败）"
        
        # 发送 SIGINT
        os.kill(pid, signal.SIGINT)
        
        # 等待退出
        proc.communicate(timeout=10)
        
        # 验证端口被释放
        time.sleep(0.2)
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = test_sock.connect_ex(("127.0.0.1", port))
        test_sock.close()
        assert result != 0, f"端口 {port} 仍未被释放"
    
    def test_sigterm_handling(self, tmp_path):
        """
        测试 SIGTERM 信号处理（kill 命令）
        
        期望：与 SIGINT 相同，优雅关闭
        """
        main_script = tmp_path / "sigterm_test.py"
        main_script.write_text('''
import os
import sys
import time
import signal
import multiprocessing

def worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(0.1)

if __name__ == "__main__":
    p = multiprocessing.Process(target=worker)
    p.start()
    
    with open("sigterm_pid.txt", "w") as f:
        f.write(f"{os.getpid()}\\n{p.pid}\\n")
    
    def handler(signum, frame):
        print(f"[Main] 收到信号 {signum}")
        p.terminate()
        p.join(timeout=2)
        if p.is_alive():
            p.kill()
        sys.exit(0)
    
    # SIGTERM 也应该被处理
    signal.signal(signal.SIGTERM, handler)
    
    while True:
        time.sleep(1)
''')
        
        proc = subprocess.Popen(
            [sys.executable, str(main_script)],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        pid_file = tmp_path / "sigterm_pid.txt"
        for _ in range(50):
            if pid_file.exists():
                break
            time.sleep(0.1)
        
        lines = pid_file.read_text().strip().split('\n')
        main_pid = int(lines[0])
        child_pid = int(lines[1])
        
        # 发送 SIGTERM 而不是 SIGINT
        os.kill(main_pid, signal.SIGTERM)
        
        stdout, stderr = proc.communicate(timeout=10)
        
        # 验证正常退出
        assert proc.returncode == 0
        assert not psutil.pid_exists(child_pid)
