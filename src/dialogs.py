from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                           QLineEdit, QPushButton, QComboBox, QMessageBox,
                           QTableWidget, QTableWidgetItem, QHeaderView,
                           QFileDialog, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSlot
from datetime import datetime
from scanner import BarcodeScanner

class AddProductDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner = BarcodeScanner()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('添加商品')
        layout = QVBoxLayout(self)
        
        # 条码输入
        barcode_layout = QHBoxLayout()
        barcode_label = QLabel('条码:')
        self.barcode_input = QLineEdit()
        scan_btn = QPushButton('扫码')
        scan_btn.clicked.connect(self.toggle_scanner)
        barcode_layout.addWidget(barcode_label)
        barcode_layout.addWidget(self.barcode_input)
        barcode_layout.addWidget(scan_btn)
        layout.addLayout(barcode_layout)
        
        # 型号输入
        model_layout = QHBoxLayout()
        model_label = QLabel('型号:')
        self.model_input = QLineEdit()
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_input)
        layout.addLayout(model_layout)
        
        # 价格输入
        price_layout = QHBoxLayout()
        price_label = QLabel('价格:')
        self.price_input = QLineEdit()
        price_layout.addWidget(price_label)
        price_layout.addWidget(self.price_input)
        layout.addLayout(price_layout)
        
        # 库存输入
        stock_layout = QHBoxLayout()
        stock_label = QLabel('库存:')
        self.stock_input = QLineEdit()
        stock_layout.addWidget(stock_label)
        stock_layout.addWidget(self.stock_input)
        layout.addLayout(stock_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton('确定')
        cancel_button = QPushButton('取消')
        ok_button.clicked.connect(self.validate_and_accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
    def toggle_scanner(self):
        sender = self.sender()
        if not self.scanner.is_running:
            if self.scanner.start(callback=self.on_barcode_scanned):
                sender.setText('停止扫码')
                QMessageBox.information(self, '提示', '已开始监控Pictures文件夹，等待扫码结果...')
        else:
            self.scanner.stop()
            sender.setText('扫码')

    @pyqtSlot(str)
    def on_barcode_scanned(self, barcode):
        """处理扫码结果"""
        self.barcode_input.setText(barcode)
        # 停止扫码
        self.scanner.stop()
        # 恢复按钮文字
        for child in self.children():
            if isinstance(child, QPushButton) and child.text() == '停止扫码':
                child.setText('扫码')
                break
        # 显示成功提示
        QMessageBox.information(self, '成功', f'扫码成功！\n条码: {barcode}')
        
    def validate_and_accept(self):
        # 验证输入
        if not self.barcode_input.text().strip():
            QMessageBox.warning(self, '错误', '请输入商品条码')
            return
        if not self.model_input.text().strip():
            QMessageBox.warning(self, '错误', '请输入商品型号')
            return
            
        try:
            price = float(self.price_input.text())
            if price <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, '错误', '请输入有效的价格')
            return
            
        try:
            stock = int(self.stock_input.text())
            if stock < 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, '错误', '请输入有效的库存数量')
            return
            
        self.accept()
        
    def get_product_data(self):
        try:
            return {
                'barcode': self.barcode_input.text().strip(),
                'model': self.model_input.text().strip(),
                'price': float(self.price_input.text()),
                'stock': int(self.stock_input.text())
            }
        except ValueError:
            return None

    def closeEvent(self, event):
        """对话框关闭时停止扫码"""
        if self.scanner.is_running:
            self.scanner.stop()
        super().closeEvent(event)

class PaymentDialog(QDialog):
    def __init__(self, total_amount, parent=None):
        super().__init__(parent)
        self.total_amount = total_amount
        self.payment_method = None
        self.scanner = BarcodeScanner()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('支付')
        layout = QVBoxLayout(self)
        
        # 显示总金额
        amount_label = QLabel(f'支付金额: ¥{self.total_amount:.2f}')
        layout.addWidget(amount_label)
        
        # 支付方式选择
        method_layout = QHBoxLayout()
        method_label = QLabel('支付方式:')
        self.method_combo = QComboBox()
        self.method_combo.addItems(['现金', '微信支付', '支付宝', '会员卡'])
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.method_combo)
        layout.addLayout(method_layout)
        
        # 会员卡号/付款码扫描
        scan_layout = QHBoxLayout()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText('会员卡号/付款码')
        scan_btn = QPushButton('扫码')
        scan_btn.clicked.connect(self.toggle_scanner)
        scan_layout.addWidget(self.code_input)
        scan_layout.addWidget(scan_btn)
        layout.addLayout(scan_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton('确认支付')
        cancel_button = QPushButton('取消')
        ok_button.clicked.connect(self.process_payment)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # 连接支付方式变化信号
        self.method_combo.currentTextChanged.connect(self.on_payment_method_changed)
        # 初始化界面状态
        self.on_payment_method_changed(self.method_combo.currentText())
        
    def on_payment_method_changed(self, method):
        """处理支付方式变化"""
        need_scan = method in ['微信支付', '支付宝', '会员卡']
        self.code_input.setEnabled(need_scan)
        for child in self.children():
            if isinstance(child, QPushButton) and child.text() in ['扫码', '停止扫码']:
                child.setEnabled(need_scan)
                
    def toggle_scanner(self):
        sender = self.sender()
        if not self.scanner.is_running:
            if self.scanner.start(callback=self.on_code_scanned):
                sender.setText('停止扫码')
                QMessageBox.information(self, '提示', '已开始监控Pictures文件夹，等待扫码结果...')
        else:
            self.scanner.stop()
            sender.setText('扫码')

    @pyqtSlot(str)
    def on_code_scanned(self, code):
        """处理扫码结果"""
        self.code_input.setText(code)
        # 停止扫码
        self.scanner.stop()
        # 恢复按钮文字
        for child in self.children():
            if isinstance(child, QPushButton) and child.text() == '停止扫码':
                child.setText('扫码')
                break
        # 显示成功提示
        QMessageBox.information(self, '成功', '扫码成功！')
        
    def process_payment(self):
        self.payment_method = self.method_combo.currentText()
        payment_code = self.code_input.text().strip()
        
        # 验证支付信息
        if self.payment_method in ['微信支付', '支付宝', '会员卡'] and not payment_code:
            QMessageBox.warning(self, '错误', '请扫描付款码或会员卡号')
            return
            
        # TODO: 实际支付处理逻辑
        success_msg = f'支付成功！\n金额: ¥{self.total_amount:.2f}\n方式: {self.payment_method}'
        if payment_code:
            success_msg += f'\n付款码/卡号: {payment_code}'
        QMessageBox.information(self, '成功', success_msg)
        self.accept()

    def closeEvent(self, event):
        """对话框关闭时停止扫码"""
        if self.scanner.is_running:
            self.scanner.stop()
        super().closeEvent(event)

class EditProductDialog(QDialog):
    def __init__(self, product_data, parent=None):
        super().__init__(parent)
        self.product_data = product_data
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('编辑商品')
        layout = QVBoxLayout(self)
        
        # 条码输入
        barcode_layout = QHBoxLayout()
        barcode_label = QLabel('条码:')
        self.barcode_input = QLineEdit()
        self.barcode_input.setText(self.product_data[1])
        barcode_layout.addWidget(barcode_label)
        barcode_layout.addWidget(self.barcode_input)
        layout.addLayout(barcode_layout)
        
        # 型号输入
        model_layout = QHBoxLayout()
        model_label = QLabel('型号:')
        self.model_input = QLineEdit()
        self.model_input.setText(self.product_data[2])
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_input)
        layout.addLayout(model_layout)
        
        # 价格输入
        price_layout = QHBoxLayout()
        price_label = QLabel('价格:')
        self.price_input = QLineEdit()
        self.price_input.setText(str(self.product_data[3]))
        price_layout.addWidget(price_label)
        price_layout.addWidget(self.price_input)
        layout.addLayout(price_layout)
        
        # 库存输入
        stock_layout = QHBoxLayout()
        stock_label = QLabel('库存:')
        self.stock_input = QLineEdit()
        self.stock_input.setText(str(self.product_data[4]))
        stock_layout.addWidget(stock_label)
        stock_layout.addWidget(self.stock_input)
        layout.addLayout(stock_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton('确定')
        cancel_button = QPushButton('取消')
        ok_button.clicked.connect(self.validate_and_accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
    def validate_and_accept(self):
        # 验证输入
        if not self.barcode_input.text().strip():
            QMessageBox.warning(self, '错误', '请输入商品条码')
            return
        if not self.model_input.text().strip():
            QMessageBox.warning(self, '错误', '请输入商品型号')
            return
            
        try:
            price = float(self.price_input.text())
            if price <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, '错误', '请输入有效的价格')
            return
            
        try:
            stock = int(self.stock_input.text())
            if stock < 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, '错误', '请输入有效的库存数量')
            return
            
        self.accept()
        
    def get_product_data(self):
        try:
            return {
                'id': self.product_data[0],
                'barcode': self.barcode_input.text().strip(),
                'model': self.model_input.text().strip(),
                'price': float(self.price_input.text()),
                'stock': int(self.stock_input.text())
            }
        except ValueError:
            return None

class SalesStatisticsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle('销售统计')
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('销售统计功能开发中...'))
        
        # 关闭按钮
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

class CategoryDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('商品分类管理')
        self.setGeometry(100, 100, 500, 400)
        
        layout = QVBoxLayout(self)
        
        # 添加分类区域
        add_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('分类名称')
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText('分类描述')
        add_btn = QPushButton('添加')
        add_btn.clicked.connect(self.add_category)
        add_layout.addWidget(self.name_input)
        add_layout.addWidget(self.desc_input)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)
        
        # 分类列表
        self.category_table = QTableWidget()
        self.category_table.setColumnCount(3)
        self.category_table.setHorizontalHeaderLabels(['ID', '名称', '描述'])
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.category_table)
        
        self.load_categories()
        
    def load_categories(self):
        categories = self.db.get_all_categories()
        self.category_table.setRowCount(len(categories))
        for row, category in enumerate(categories):
            self.category_table.setItem(row, 0, QTableWidgetItem(str(category[0])))
            self.category_table.setItem(row, 1, QTableWidgetItem(category[1]))
            self.category_table.setItem(row, 2, QTableWidgetItem(category[2] or ''))
            
    def add_category(self):
        name = self.name_input.text().strip()
        desc = self.desc_input.text().strip()
        if name:
            try:
                self.db.add_category(name, desc)
                self.name_input.clear()
                self.desc_input.clear()
                self.load_categories()
            except Exception as e:
                QMessageBox.warning(self, '错误', f'添加分类失败: {str(e)}')

class MemberDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('会员管理')
        self.setGeometry(100, 100, 600, 400)
        
        layout = QVBoxLayout(self)
        
        # 添加会员区域
        add_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('会员姓名')
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText('手机号码')
        add_btn = QPushButton('添加')
        add_btn.clicked.connect(self.add_member)
        add_layout.addWidget(self.name_input)
        add_layout.addWidget(self.phone_input)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)
        
        # 会员查询
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('输入手机号码查询')
        search_btn = QPushButton('查询')
        search_btn.clicked.connect(self.search_member)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        # 会员信息显示
        self.info_label = QLabel()
        layout.addWidget(self.info_label)
        
    def add_member(self):
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        if name and phone:
            try:
                self.db.add_member(name, phone)
                self.name_input.clear()
                self.phone_input.clear()
                QMessageBox.information(self, '成功', '会员添加成功！')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'添加会员失败: {str(e)}')
                
    def search_member(self):
        phone = self.search_input.text().strip()
        if phone:
            member = self.db.get_member_by_phone(phone)
            if member:
                info = f'''
                会员信息：
                姓名：{member[1]}
                手机：{member[2]}
                积分：{member[3]}
                等级：{member[4]}
                注册时间：{member[5]}
                '''
                self.info_label.setText(info)
            else:
                self.info_label.setText('未找到会员信息')

class ImportExportDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('导入导出')
        self.setGeometry(100, 100, 400, 300)
        
        layout = QVBoxLayout(self)
        
        # 商品导入导出
        layout.addWidget(QLabel('商品数据：'))
        product_layout = QHBoxLayout()
        import_btn = QPushButton('导入商品')
        export_btn = QPushButton('导出商品')
        import_btn.clicked.connect(self.import_products)
        export_btn.clicked.connect(self.export_products)
        product_layout.addWidget(import_btn)
        product_layout.addWidget(export_btn)
        layout.addLayout(product_layout)
        
        # 订单导出
        layout.addWidget(QLabel('订单数据：'))
        order_layout = QHBoxLayout()
        export_order_btn = QPushButton('导出订单')
        export_order_btn.clicked.connect(self.export_orders)
        order_layout.addWidget(export_order_btn)
        layout.addLayout(order_layout)
        
    def import_products(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, '选择文件', '', 'CSV文件 (*.csv)')
        if filename:
            try:
                self.db.import_products_from_csv(filename)
                QMessageBox.information(self, '成功', '商品导入成功！')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'导入失败: {str(e)}')
    
    def export_products(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存文件', '', 'CSV文件 (*.csv)')
        if filename:
            try:
                self.db.export_products_to_csv(filename)
                QMessageBox.information(self, '成功', '商品导出成功！')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'导出失败: {str(e)}')
    
    def export_orders(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存文件', '', 'CSV文件 (*.csv)')
        if filename:
            try:
                self.db.export_orders_to_csv(filename)
                QMessageBox.information(self, '成功', '订单导出成功！')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'导出失败: {str(e)}') 