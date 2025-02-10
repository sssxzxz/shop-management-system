from datetime import datetime
import json
import os
from PyQt5.QtWidgets import QMessageBox
import win32print
import win32con
import win32ui
import win32gui

class ReceiptPrinter:
    def __init__(self, printer_type='windows', config_file='printer_config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.simulation_mode = True
        self.printer_name = None
        try:
            self.init_printer(printer_type)
        except Exception as e:
            print(f"打印机初始化失败: {str(e)}")
            
    def load_config(self):
        default_config = {
            'shop_name': '示例商店',
            'shop_address': '示例地址',
            'shop_phone': '示例电话',
            'footer_text': '感谢您的惠顾，欢迎再次光临！'
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return {**default_config, **json.load(f)}
            return default_config
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return default_config
            
    def init_printer(self, printer_type):
        try:
            self.printer_name = win32print.GetDefaultPrinter()
            if self.printer_name:
                print(f"已连接默认打印机: {self.printer_name}")
                self.simulation_mode = False
            else:
                raise Exception("未找到默认打印机")
        except Exception as e:
            self.printer_name = None
            print(f"打印机初始化失败: {str(e)}")
            
    def is_connected(self):
        return self.printer_name is not None and not self.simulation_mode
        
    def do_print(self, text, preview=False):
        """实际执行打印操作"""
        if preview or self.simulation_mode:
            return text
            
        try:
            print("开始打印...")
            print(f"使用打印机: {self.printer_name}")
            
            # 创建打印机DC
            print("正在连接打印机...")
            hprinter = win32print.OpenPrinter(self.printer_name)
            printer_info = win32print.GetPrinter(hprinter, 2)
            print("打印机信息:", printer_info)
            
            # 创建打印任务
            print("创建打印任务...")
            job = win32print.StartDocPrinter(hprinter, 1, ("Receipt", None, "RAW"))
            try:
                win32print.StartPagePrinter(hprinter)
                
                # 创建DC
                print("创建设备上下文...")
                dc = win32ui.CreateDC()
                dc.CreatePrinterDC(self.printer_name)
                
                # 设置打印参数
                print("设置打印参数...")
                dc.SetMapMode(win32con.MM_TWIPS)  # 1440 per inch
                
                # 获取打印机分辨率
                printer_dpi_x = dc.GetDeviceCaps(win32con.LOGPIXELSX)
                printer_dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY)
                
                # 计算页面宽度（以twips为单位）
                page_width = int(dc.GetDeviceCaps(win32con.PHYSICALWIDTH) * 1440 / printer_dpi_x)
                
                dc.StartDoc('Receipt')
                dc.StartPage()
                
                # 设置字体
                print("设置字体...")
                # 标题字体
                title_font = win32ui.CreateFont({
                    'name': '宋体',
                    'height': int(10 * 1440 / 72),  # 10pt
                    'weight': 700  # 加粗
                })
                
                # 正文字体
                content_font = win32ui.CreateFont({
                    'name': '宋体',
                    'height': int(9 * 1440 / 72),  # 9pt
                    'weight': 400
                })
                
                # 打印文本
                print("开始输出文本...")
                y = -500  # 起始位置
                title_line_height = int(15 * 1440 / 72)  # 标题行高
                content_line_height = int(12 * 1440 / 72)  # 正文行高
                
                for line in text.split('\n'):
                    # 判断是否是标题行（店铺名称）或分隔线
                    is_title = line == text.split('\n')[0] or '---' in line
                    is_separator = '---' in line
                    
                    # 选择字体
                    if is_title:
                        dc.SelectObject(title_font)
                        line_height = title_line_height
                    else:
                        dc.SelectObject(content_font)
                        line_height = content_line_height
                    
                    # 计算文本宽度
                    text_width = dc.GetTextExtent(line)[0]
                    
                    # 分隔线居中显示，其他左对齐
                    if is_separator:
                        x = (page_width - text_width) // 2
                        if x < 0:
                            x = 0
                    else:
                        x = 100  # 左边距
                    
                    # 打印文本
                    dc.TextOut(x, y, line)
                    y -= line_height
                    
                # 结束打印
                print("结束打印...")
                dc.EndPage()
                dc.EndDoc()
                
                # 清理资源
                del title_font
                del content_font
                del dc
                print("打印完成")
                
                return True
            finally:
                win32print.EndDocPrinter(hprinter)
                win32print.ClosePrinter(hprinter)
                
        except Exception as e:
            print(f"打印失败: {str(e)}")
            import traceback
            print("错误详情:")
            traceback.print_exc()
            return str(e)
            
    def print_receipt(self, order_data, items, preview=False):
        try:
            content = []
            
            # 店铺信息
            content.append(f"{self.config['shop_name']}\n")
            content.append("--------------------------------\n")
            content.append(f"地址:{self.config['shop_address']}\n")
            content.append(f"电话:{self.config['shop_phone']}\n")
            content.append("--------------------------------\n")
            
            # 订单信息
            content.append(f"订单号:{order_data['id']}\n")
            content.append(f"时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            content.append("--------------------------------\n")
            
            # 商品列表
            content.append("商品列表:\n")
            for item in items:
                # 商品名称可能较长，需要处理换行
                model = item['model']
                if len(model) > 16:  # 一行最多16个中文字符
                    model = model[:15] + '...'
                content.append(f"{model}\n")
                content.append(f"数量:{item['quantity']}×¥{item['price']:.2f}\n")
                content.append(f"小计:¥{item['quantity'] * item['price']:.2f}\n")
            
            content.append("--------------------------------\n")
            
            # 总计
            content.append(f"总计:¥{order_data['total_amount']:.2f}\n")
            content.append(f"支付方式:{order_data['payment_method']}\n")
            
            # 页脚
            content.append("--------------------------------\n")
            content.append(f"{self.config['footer_text']}\n")
            content.append("\n\n\n")  # 留出切纸空间
            
            return self.do_print(''.join(content), preview)
                
        except Exception as e:
            if not preview and not self.simulation_mode:
                raise Exception(f"打印失败: {str(e)}")
            return str(e)
            
    def test_printer(self, preview=False):
        try:
            content = [
                "打印机测试\n",
                "--------------------------------\n",
                f"店铺名称:{self.config['shop_name']}\n",
                f"打印时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                "--------------------------------\n",
                "打印机工作正常\n",
                "--------------------------------\n",
                "\n\n\n"  # 留出切纸空间
            ]
            
            return self.do_print(''.join(content), preview)
                
        except Exception as e:
            if not preview and not self.simulation_mode:
                raise Exception(f"打印测试失败: {str(e)}")
            return str(e)
            
    def update_config(self, new_config):
        self.config.update(new_config)
        return self.save_config()
        
    def get_config(self):
        return self.config.copy()
        
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
            return False 