import threading
import time
import os
from datetime import datetime, timedelta
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal

class BarcodeScanner(QObject):
    # 定义信号
    barcode_scanned = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.last_barcode = None
        self.callback = None
        self.watch_path = r"C:\Users\49482\Pictures"
        self.last_check_time = None
        self.processed_files = set()  # 记录已处理的文件
        self.parent_widget = None  # 用于显示消息框的父窗口
        
    def start(self, callback=None, parent=None):
        """启动扫码器"""
        if self.is_running:
            print("扫码器已经在运行")
            return False

        print("启动扫码器")
        self.is_running = True
        self.callback = callback
        self.parent_widget = parent
        self.last_check_time = datetime.now()
        self.processed_files.clear()  # 清空已处理文件列表
        
        # 连接信号到回调函数
        if callback:
            self.barcode_scanned.connect(callback)
        
        # 在新线程中运行监控循环
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        return True

    def stop(self):
        """停止扫码器"""
        print("停止扫码器")
        self.is_running = False
        # 断开信号连接
        try:
            if self.callback:
                self.barcode_scanned.disconnect(self.callback)
        except:
            pass

    def show_message(self, title, message):
        """显示消息框"""
        if self.parent_widget:
            # 使用invokeMethod在主线程中显示消息框
            self.parent_widget.metaObject().invokeMethod(
                self.parent_widget, 
                "showMessageBox",
                Qt.QueuedConnection,
                Q_ARG(str, title),
                Q_ARG(str, message)
            )

    def _monitor_loop(self):
        """监控文件夹循环"""
        print(f"开始监控文件夹: {self.watch_path}")
        while self.is_running:
            try:
                # 获取文件夹中的所有可能的条码文件
                current_files = []
                for f in os.listdir(self.watch_path):
                    if not f in self.processed_files:  # 只处理未处理过的文件
                        file_path = os.path.join(self.watch_path, f)
                        # 检查文件名是否包含关键字
                        if ('商品' in f or '条形码' in f or 'barcode' in f) and f.endswith('.txt'):
                            current_files.append(f)
                            print(f"发现新文件: {f}")
                
                if not current_files:
                    time.sleep(0.2)
                    continue
                
                # 按修改时间排序
                current_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.watch_path, x)))
                
                # 处理新文件
                for file_name in current_files:
                    if file_name in self.processed_files:
                        continue
                        
                    file_path = os.path.join(self.watch_path, file_name)
                    if not os.path.exists(file_path):
                        self.processed_files.add(file_name)
                        continue
                        
                    try:
                        # 等待文件写入完成
                        time.sleep(0.1)
                        
                        # 尝试打开并读取文件
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                barcode = f.read().strip()
                        except UnicodeDecodeError:
                            # 如果UTF-8解码失败，尝试其他编码
                            with open(file_path, 'r', encoding='gbk') as f:
                                barcode = f.read().strip()
                                
                        if barcode:
                            print(f"读取到条码: {barcode}")
                            self.last_barcode = barcode
                            # 发送信号而不是直接调用回调
                            self.barcode_scanned.emit(barcode)
                        
                        # 将文件添加到已处理列表
                        self.processed_files.add(file_name)
                        
                        # 处理完后删除文件
                        try:
                            os.remove(file_path)
                            print(f"已删除文件: {file_name}")
                        except OSError as e:
                            print(f"删除文件失败: {str(e)}")
                            
                    except Exception as e:
                        print(f"处理文件 {file_name} 时出错: {str(e)}")
                        # 如果处理失败，也将文件加入已处理列表，避免重复处理
                        self.processed_files.add(file_name)
                
            except Exception as e:
                print(f"监控循环出错: {str(e)}")
            
            # 短暂休眠
            time.sleep(0.2)
        
        print("监控循环结束")

    def get_last_barcode(self):
        """获取最后一次扫描到的条形码"""
        return self.last_barcode 