import sys
import os
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel, QLineEdit,
                           QTableWidget, QTableWidgetItem, QMessageBox,
                           QSpinBox, QDialog, QHeaderView, QComboBox,
                           QTextEdit, QAction)
from PyQt5.QtCore import Qt, pyqtSlot
from models import Database
from scanner import BarcodeScanner
from printer import ReceiptPrinter
from dialogs import (AddProductDialog, PaymentDialog, EditProductDialog, 
                    SalesStatisticsDialog, CategoryDialog, MemberDialog,
                    ImportExportDialog)
from datetime import datetime
import psutil
import time

class SingleInstanceChecker:
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_handle = None

    def try_lock(self):
        try:
            # 检查是否有其他Python进程运行main.py
            current_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'python.exe' and proc.pid != current_pid:
                        cmdline = proc.info['cmdline']
                        if cmdline and 'main.py' in cmdline[-1]:
                            # 尝试终止已存在的进程
                            try:
                                proc.terminate()
                                proc.wait(timeout=3)  # 等待进程终止
                            except psutil.TimeoutExpired:
                                proc.kill()  # 如果等待超时，强制结束进程
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 创建锁文件
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
            
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            print(f"锁定失败: {str(e)}")
            return False

    def release(self):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except:
            pass

    @staticmethod
    def terminate_existing_instances():
        current_pid = os.getpid()
        current_process = psutil.Process(current_pid)
        current_cmdline = ' '.join(current_process.cmdline())
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid != current_pid and proc.info['name'] == 'python.exe':
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'main.py' in cmdline:
                        proc.terminate()
                        proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue

class OrderHistoryDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.printer = parent.printer if parent else None
        self.parent = parent
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('订单历史')
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout(self)
        
        # 订单列表
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(4)
        self.order_table.setHorizontalHeaderLabels(['订单号', '交易时间', '订单金额', '支付方式'])
        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.order_table)
        
        # 订单详情
        detail_label = QLabel('订单商品明细:')
        layout.addWidget(detail_label)
        
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(4)
        self.detail_table.setHorizontalHeaderLabels(['商品型号', '单价', '购买数量', '商品小计'])
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.detail_table)
        
        # 添加打印按钮
        button_layout = QHBoxLayout()
        print_selected_btn = QPushButton('打印选中订单')
        print_all_btn = QPushButton('打印所有订单')
        close_btn = QPushButton('关闭')
        
        print_selected_btn.clicked.connect(self.print_selected_order)
        print_all_btn.clicked.connect(self.print_all_orders)
        close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(print_selected_btn)
        button_layout.addWidget(print_all_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        self.load_orders()
        
        # 选择订单时显示详情
        self.order_table.itemSelectionChanged.connect(self.show_order_details)
        
    def load_orders(self):
        orders = self.db.get_all_orders()
        self.order_table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            # 将订单号格式化为5位数
            self.order_table.setItem(row, 0, QTableWidgetItem(f"{order[0]:05d}"))
            self.order_table.setItem(row, 1, QTableWidgetItem(order[1]))
            self.order_table.setItem(row, 2, QTableWidgetItem(f"¥{order[2]:.2f}"))
            self.order_table.setItem(row, 3, QTableWidgetItem(order[3]))
            
    def show_order_details(self):
        selected_items = self.order_table.selectedItems()
        if not selected_items:
            return
            
        # 将显示的5位数订单号转换回整数
        order_id = int(self.order_table.item(self.order_table.currentRow(), 0).text())
        details = self.db.get_order_details(order_id)
        
        self.detail_table.setRowCount(len(details))
        for row, detail in enumerate(details):
            self.detail_table.setItem(row, 0, QTableWidgetItem(detail['model']))
            self.detail_table.setItem(row, 1, QTableWidgetItem(f"¥{detail['price']:.2f}"))
            self.detail_table.setItem(row, 2, QTableWidgetItem(str(detail['quantity'])))
            self.detail_table.setItem(row, 3, QTableWidgetItem(f"¥{detail['price'] * detail['quantity']:.2f}"))

    def print_selected_order(self):
        """打印选中的订单"""
        selected_items = self.order_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '警告', '请先选择要打印的订单')
            return
            
        row = self.order_table.currentRow()
        order_id = int(self.order_table.item(row, 0).text())
        order_data = {
            'id': f"{order_id:05d}",  # 格式化订单号为5位数
            'total_amount': float(self.order_table.item(row, 2).text().replace('¥', '')),
            'payment_method': self.order_table.item(row, 3).text()
        }
        
        # 获取订单详情
        items = self.db.get_order_details(order_id)
        
        if self.printer:
            try:
                if self.printer.print_receipt(order_data, items):
                    QMessageBox.information(self, '成功', '打印已发送')
                else:
                    QMessageBox.warning(self, '错误', '打印失败')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'打印失败: {str(e)}')
        else:
            QMessageBox.warning(self, '错误', '打印机未初始化')
            
    def print_all_orders(self):
        """打印所有订单"""
        if self.order_table.rowCount() == 0:
            QMessageBox.warning(self, '警告', '没有可打印的订单')
            return
            
        reply = QMessageBox.question(self, '确认', 
                                   f'确定要打印全部 {self.order_table.rowCount()} 条订单记录吗？',
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success_count = 0
            fail_count = 0
            
            for row in range(self.order_table.rowCount()):
                order_id = int(self.order_table.item(row, 0).text())
                order_data = {
                    'id': f"{order_id:05d}",  # 格式化订单号为5位数
                    'total_amount': float(self.order_table.item(row, 2).text().replace('¥', '')),
                    'payment_method': self.order_table.item(row, 3).text()
                }
                
                items = self.db.get_order_details(order_id)
                
                if self.printer:
                    try:
                        if self.printer.print_receipt(order_data, items):
                            success_count += 1
                        else:
                            fail_count += 1
                    except:
                        fail_count += 1
                else:
                    QMessageBox.warning(self, '错误', '打印机未初始化')
                    return
            
            QMessageBox.information(self, '完成', 
                                  f'打印完成\n成功: {success_count}\n失败: {fail_count}')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.scanner = BarcodeScanner()
        self.printer = ReceiptPrinter()
        self.current_order_items = []
        
        self.init_ui()
        self.check_low_stock()
        
    def init_ui(self):
        self.setWindowTitle('商店管理系统')
        self.setGeometry(100, 100, 1024, 768)

        # 创建菜单栏
        menubar = self.menuBar()
        
        # 菜单
        menu = menubar.addMenu('菜单')
        
        # 小票设置
        printer_action = QAction('小票设置', self)
        printer_action.triggered.connect(self.show_printer_config)
        menu.addAction(printer_action)
        
        # 测试打印
        test_print_action = QAction('测试打印', self)
        test_print_action.triggered.connect(self.test_print_sample)
        menu.addAction(test_print_action)
        
        # 退出
        exit_action = QAction('退出', self)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # 左侧面板 - 商品管理
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 管理按钮
        button_layout = QHBoxLayout()
        add_product_btn = QPushButton('添加商品')
        view_history_btn = QPushButton('查看历史订单')
        stats_btn = QPushButton('销售统计')
        
        add_product_btn.clicked.connect(self.show_add_product_dialog)
        view_history_btn.clicked.connect(self.show_order_history)
        stats_btn.clicked.connect(self.show_sales_statistics)
        
        button_layout.addWidget(add_product_btn)
        button_layout.addWidget(view_history_btn)
        button_layout.addWidget(stats_btn)
        left_layout.addLayout(button_layout)
        
        # 商品搜索
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('输入条码或型号搜索')
        self.search_input.returnPressed.connect(self.search_products)
        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self.search_products)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        left_layout.addLayout(search_layout)
        
        # 商品列表
        self.product_table = QTableWidget()
        self.product_table.setColumnCount(5)
        self.product_table.setHorizontalHeaderLabels(['条码', '型号', '价格', '库存', '操作'])
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.product_table.itemDoubleClicked.connect(self.on_product_double_clicked)
        left_layout.addWidget(self.product_table)
        
        layout.addWidget(left_panel)

        # 右侧面板 - 收银
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 扫码区域
        scan_widget = QWidget()
        scan_layout = QHBoxLayout(scan_widget)
        self.barcode_input = QLineEdit()
        self.barcode_input.returnPressed.connect(self.on_barcode_entered)
        scan_btn = QPushButton('开始扫码')
        scan_btn.clicked.connect(self.toggle_scanner)
        scan_layout.addWidget(self.barcode_input)
        scan_layout.addWidget(scan_btn)
        right_layout.addWidget(scan_widget)
        
        # 当前订单
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(5)
        self.order_table.setHorizontalHeaderLabels(['商品', '单价', '数量', '小计', '操作'])
        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.order_table)
        
        # 订单总计
        total_widget = QWidget()
        total_layout = QHBoxLayout(total_widget)
        self.total_label = QLabel('总计: ¥0.00')
        total_layout.addWidget(self.total_label)
        right_layout.addWidget(total_widget)
        
        # 支付按钮
        pay_btn = QPushButton('支付')
        pay_btn.clicked.connect(self.process_payment)
        right_layout.addWidget(pay_btn)
        
        layout.addWidget(right_panel)
        
        self.update_product_table()

    def toggle_scanner(self):
        if not self.scanner.is_running:
            if self.scanner.start(callback=self.on_barcode_scanned):
                self.sender().setText('停止扫码')
                QMessageBox.information(self, '提示', '已开始监控Pictures文件夹，等待扫码结果...')
        else:
            self.scanner.stop()
            self.sender().setText('开始扫码')

    def on_barcode_entered(self):
        barcode = self.barcode_input.text().strip()
        if barcode:
            self.add_item_to_order(barcode)
            self.barcode_input.clear()

    def show_order_history(self):
        dialog = OrderHistoryDialog(self.db, self)
        dialog.exec_()

    def update_order_table(self):
        self.order_table.setRowCount(len(self.current_order_items))
        total = 0
        
        for row, item in enumerate(self.current_order_items):
            self.order_table.setItem(row, 0, QTableWidgetItem(item['model']))
            self.order_table.setItem(row, 1, QTableWidgetItem(f"¥{item['price']:.2f}"))
            
            # 数量调整
            quantity_spin = QSpinBox()
            quantity_spin.setMinimum(1)
            quantity_spin.setMaximum(999)
            quantity_spin.setValue(item['quantity'])
            quantity_spin.valueChanged.connect(lambda value, row=row: self.update_item_quantity(row, value))
            self.order_table.setCellWidget(row, 2, quantity_spin)
            
            subtotal = item['price'] * item['quantity']
            self.order_table.setItem(row, 3, QTableWidgetItem(f"¥{subtotal:.2f}"))
            
            # 删除按钮
            delete_btn = QPushButton('删除')
            delete_btn.clicked.connect(lambda checked, row=row: self.delete_order_item(row))
            self.order_table.setCellWidget(row, 4, delete_btn)
            
            total += subtotal
        
        self.total_label.setText(f'总计: ¥{total:.2f}')

    def update_item_quantity(self, row, value):
        if 0 <= row < len(self.current_order_items):
            self.current_order_items[row]['quantity'] = value
            self.update_order_table()

    def delete_order_item(self, row):
        if 0 <= row < len(self.current_order_items):
            self.current_order_items.pop(row)
            self.update_order_table()

    def show_add_product_dialog(self):
        dialog = AddProductDialog(self)
        if dialog.exec() == AddProductDialog.DialogCode.Accepted:
            product_data = dialog.get_product_data()
            if product_data:
                try:
                    self.db.add_product(
                        product_data['barcode'],
                        product_data['model'],
                        product_data['price'],
                        product_data['stock']
                    )
                    self.update_product_table()
                except Exception as e:
                    QMessageBox.warning(self, '错误', f'添加商品失败: {str(e)}')

    def on_barcode_scanned(self, barcode):
        self.barcode_input.setText(barcode)
        self.add_item_to_order(barcode)

    def add_item_to_order(self, barcode):
        product = self.db.get_product_by_barcode(barcode)
        if not product:
            QMessageBox.warning(self, '错误', '商品不存在')
            return

        # 检查是否已经在订单中
        for item in self.current_order_items:
            if item['product_id'] == product[0]:
                item['quantity'] += 1
                self.update_order_table()
                return

        # 添加到订单列表
        item = {
            'product_id': product[0],
            'model': product[2],
            'price': product[3],
            'quantity': 1
        }
        self.current_order_items.append(item)
        self.update_order_table()

    def update_product_table(self, products=None):
        if products is None:
            cursor = self.db.conn.cursor()
            cursor.execute('SELECT * FROM products')
            products = cursor.fetchall()
        
        self.product_table.setRowCount(len(products))
        for row, product in enumerate(products):
            # 存储商品ID
            barcode_item = QTableWidgetItem(product[1])
            barcode_item.setData(Qt.UserRole, product[0])
            self.product_table.setItem(row, 0, barcode_item)
            
            self.product_table.setItem(row, 1, QTableWidgetItem(product[2]))  # 型号
            self.product_table.setItem(row, 2, QTableWidgetItem(f"¥{product[3]:.2f}"))  # 价格
            self.product_table.setItem(row, 3, QTableWidgetItem(str(product[4])))  # 库存
            
            # 编辑按钮
            edit_btn = QPushButton('编辑')
            edit_btn.clicked.connect(lambda checked, row=row: self.on_product_double_clicked(self.product_table.item(row, 0)))
            self.product_table.setCellWidget(row, 4, edit_btn)

    def process_payment(self):
        if not self.current_order_items:
            QMessageBox.warning(self, '错误', '订单为空')
            return

        total = sum(item['price'] * item['quantity'] for item in self.current_order_items)
        dialog = PaymentDialog(total, self)
        
        if dialog.exec() == PaymentDialog.DialogCode.Accepted:
            # 停止扫码器
            if self.scanner.is_running:
                self.scanner.stop()
                # 恢复扫码按钮状态
                for child in self.findChildren(QPushButton):
                    if child.text() == '停止扫码':
                        child.setText('开始扫码')
                        break
            
            # 创建订单
            order_id = self.db.create_order(self.current_order_items, dialog.payment_method)
            
            # 打印小票
            if not self.printer:
                try:
                    self.printer = ReceiptPrinter()
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'打印机初始化失败: {str(e)}')
            
            if self.printer:
                order_data = {
                    'id': f"{order_id:05d}",  # 格式化订单号为5位数
                    'total_amount': total,
                    'payment_method': dialog.payment_method
                }
                try:
                    self.printer.print_receipt(order_data, self.current_order_items)
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'打印失败: {str(e)}')
            
            # 清空当前订单
            self.current_order_items = []
            self.update_order_table()
            self.update_product_table()
            QMessageBox.information(self, '成功', '交易完成！')

    def check_low_stock(self):
        """
        检查库存预警
        """
        low_stock_products = self.db.get_low_stock_products()
        if low_stock_products:
            message = "以下商品库存不足：\n"
            for product in low_stock_products:
                message += f"- {product[2]}（库存：{product[4]}）\n"
            QMessageBox.warning(self, '库存预警', message)

    def search_products(self):
        """
        搜索商品
        """
        keyword = self.search_input.text().strip()
        if keyword:
            products = self.db.search_products(keyword)
            self.update_product_table(products)
        else:
            self.update_product_table()

    def show_sales_statistics(self):
        """
        显示销售统计
        """
        dialog = SalesStatisticsDialog(self.db, self)
        dialog.exec_()

    def on_product_double_clicked(self, item):
        """
        双击商品行时编辑商品
        """
        row = item.row()
        product_data = [
            int(self.product_table.item(row, 0).data(Qt.UserRole)),  # id
            self.product_table.item(row, 0).text(),  # barcode
            self.product_table.item(row, 1).text(),  # model
            float(self.product_table.item(row, 2).text().replace('¥', '')),  # price
            int(self.product_table.item(row, 3).text())  # stock
        ]
        
        dialog = EditProductDialog(product_data, self)
        if dialog.exec() == EditProductDialog.DialogCode.Accepted:
            product_data = dialog.get_product_data()
            if product_data:
                try:
                    self.db.update_product(
                        product_data['id'],
                        barcode=product_data['barcode'],
                        model=product_data['model'],
                        price=product_data['price'],
                        stock=product_data['stock']
                    )
                    self.update_product_table()
                except Exception as e:
                    QMessageBox.warning(self, '错误', f'更新商品失败: {str(e)}')

    def show_category_dialog(self):
        dialog = CategoryDialog(self.db, self)
        dialog.exec_()
        self.update_product_table()  # 刷新商品列表

    def show_member_dialog(self):
        dialog = MemberDialog(self.db, self)
        dialog.exec_()

    def show_import_export_dialog(self):
        dialog = ImportExportDialog(self.db, self)
        dialog.exec_()
        self.update_product_table()  # 刷新商品列表

    def test_print_sample(self):
        """测试打印样例数据"""
        try:
            # 创建测试订单数据
            order_data = {
                'id': '00001',  # 使用5位数的订单号
                'total_amount': 299.99,
                'payment_method': '现金'
            }
            
            # 创建测试商品列表
            items = [
                {
                    'model': '测试商品1',
                    'quantity': 2,
                    'price': 99.99
                },
                {
                    'model': '测试商品2',
                    'quantity': 1,
                    'price': 100.01
                }
            ]
            
            # 先显示预览
            preview_text = self.printer.print_receipt(order_data, items, preview=True)
            
            # 创建预览对话框
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle('打印预览')
            preview_dialog.setGeometry(150, 150, 400, 600)
            
            layout = QVBoxLayout(preview_dialog)
            
            # 预览文本
            preview = QTextEdit()
            preview.setReadOnly(True)
            preview.setPlainText(preview_text)
            layout.addWidget(preview)
            
            # 按钮布局
            button_layout = QHBoxLayout()
            
            # 打印按钮
            print_btn = QPushButton('打印')
            print_btn.clicked.connect(lambda: self.do_print_sample(order_data, items, preview_dialog))
            
            # 关闭按钮
            close_btn = QPushButton('关闭')
            close_btn.clicked.connect(preview_dialog.close)
            
            button_layout.addWidget(print_btn)
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout)
            
            preview_dialog.exec_()
            
        except Exception as e:
            QMessageBox.warning(self, '错误', f'打印预览失败: {str(e)}')
            
    def do_print_sample(self, order_data, items, dialog):
        """执行实际打印"""
        try:
            if self.printer.print_receipt(order_data, items):
                QMessageBox.information(self, '成功', '打印已发送')
                dialog.accept()
            else:
                QMessageBox.warning(self, '错误', '打印失败')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'打印失败: {str(e)}')

    def show_printer_config(self):
        """显示小票设置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle('小票设置')
        dialog.setGeometry(300, 300, 400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 店铺信息设置
        form_layout = QVBoxLayout()
        
        # 店铺名称
        shop_name_layout = QHBoxLayout()
        shop_name_label = QLabel('店铺名称:')
        self.shop_name_input = QLineEdit()
        self.shop_name_input.setText(self.printer.config['shop_name'])
        shop_name_layout.addWidget(shop_name_label)
        shop_name_layout.addWidget(self.shop_name_input)
        form_layout.addLayout(shop_name_layout)
        
        # 店铺地址
        shop_address_layout = QHBoxLayout()
        shop_address_label = QLabel('店铺地址:')
        self.shop_address_input = QLineEdit()
        self.shop_address_input.setText(self.printer.config['shop_address'])
        shop_address_layout.addWidget(shop_address_label)
        shop_address_layout.addWidget(self.shop_address_input)
        form_layout.addLayout(shop_address_layout)
        
        # 联系电话
        shop_phone_layout = QHBoxLayout()
        shop_phone_label = QLabel('联系电话:')
        self.shop_phone_input = QLineEdit()
        self.shop_phone_input.setText(self.printer.config['shop_phone'])
        shop_phone_layout.addWidget(shop_phone_label)
        shop_phone_layout.addWidget(self.shop_phone_input)
        form_layout.addLayout(shop_phone_layout)
        
        # 页脚文本
        footer_layout = QHBoxLayout()
        footer_label = QLabel('页脚文本:')
        self.footer_input = QLineEdit()
        self.footer_input.setText(self.printer.config['footer_text'])
        footer_layout.addWidget(footer_label)
        footer_layout.addWidget(self.footer_input)
        form_layout.addLayout(footer_layout)
        
        layout.addLayout(form_layout)
        
        # 打印机信息显示
        printer_info = QLabel(f'当前打印机: {self.printer.printer_name or "未连接"}')
        layout.addWidget(printer_info)
        
        # 测试打印按钮
        test_btn = QPushButton('测试打印')
        test_btn.clicked.connect(self.test_print)
        layout.addWidget(test_btn)
        
        # 保存按钮
        button_layout = QHBoxLayout()
        save_btn = QPushButton('保存')
        cancel_btn = QPushButton('取消')
        
        save_btn.clicked.connect(lambda: self.save_printer_config(dialog))
        cancel_btn.clicked.connect(dialog.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        dialog.exec_()
        
    def save_printer_config(self, dialog):
        """保存打印机配置"""
        new_config = {
            'shop_name': self.shop_name_input.text(),
            'shop_address': self.shop_address_input.text(),
            'shop_phone': self.shop_phone_input.text(),
            'footer_text': self.footer_input.text()
        }
        
        if self.printer.update_config(new_config):
            QMessageBox.information(self, '成功', '打印机配置已保存')
            dialog.accept()
        else:
            QMessageBox.warning(self, '错误', '保存配置失败')
            
    def test_print(self):
        """测试打印功能"""
        try:
            result = self.printer.test_printer()
            if result is True:
                QMessageBox.information(self, '成功', '测试打印已发送')
            else:
                QMessageBox.warning(self, '警告', f'打印失败: {result}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'打印失败: {str(e)}')

if __name__ == '__main__':
    SingleInstanceChecker.terminate_existing_instances()
    # 创建锁文件路径
    lock_file = os.path.join(tempfile.gettempdir(), 'shop_management_system.lock')
    
    # 检查是否已有实例运行
    checker = SingleInstanceChecker(lock_file)
    if not checker.try_lock():
        QMessageBox.warning(None, '错误', '程序已经在运行中！')
        sys.exit(1)
        
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        app.exec_()
    finally:
        # 释放锁文件
        checker.release() 