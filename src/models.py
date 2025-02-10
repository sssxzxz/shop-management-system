import sqlite3
from datetime import datetime, timedelta
import csv
import os

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('shop.db')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # 创建商品表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE,
            model TEXT UNIQUE,
            price REAL,
            stock INTEGER
        )
        ''')

        # 创建订单表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_time DATETIME,
            total_amount REAL,
            payment_method TEXT
        )
        ''')

        # 创建订单详情表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price REAL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        ''')

        self.conn.commit()

    def add_product(self, barcode, model, price, stock):
        """添加商品，如果型号已存在则抛出异常"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO products (barcode, model, price, stock)
            VALUES (?, ?, ?, ?)
            ''', (barcode, model, price, stock))
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: products.model" in str(e):
                raise Exception("商品型号已存在")
            elif "UNIQUE constraint failed: products.barcode" in str(e):
                raise Exception("商品条码已存在")
            else:
                raise e

    def update_product(self, product_id, barcode=None, model=None, price=None, stock=None):
        """
        更新商品信息，如果型号已存在则抛出异常
        """
        try:
            # 先检查型号是否存在（如果要更新型号的话）
            if model is not None:
                cursor = self.conn.cursor()
                cursor.execute('''
                SELECT id FROM products 
                WHERE model = ? AND id != ?
                ''', (model, product_id))
                if cursor.fetchone():
                    raise Exception("商品型号已存在")

            updates = []
            values = []
            if barcode is not None:
                updates.append("barcode = ?")
                values.append(barcode)
            if model is not None:
                updates.append("model = ?")
                values.append(model)
            if price is not None:
                updates.append("price = ?")
                values.append(price)
            if stock is not None:
                updates.append("stock = ?")
                values.append(stock)
            
            if updates:
                values.append(product_id)
                cursor = self.conn.cursor()
                cursor.execute(f'''
                UPDATE products 
                SET {", ".join(updates)}
                WHERE id = ?
                ''', values)
                self.conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: products.barcode" in str(e):
                raise Exception("商品条码已存在")
            else:
                raise e

    def delete_product(self, id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (id,))
        self.conn.commit()

    def get_product_by_barcode(self, barcode):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM products WHERE barcode = ?', (barcode,))
        return cursor.fetchone()

    def create_order(self, items, payment_method):
        cursor = self.conn.cursor()
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        # 创建订单
        cursor.execute('''
        INSERT INTO orders (order_time, total_amount, payment_method)
        VALUES (?, ?, ?)
        ''', (datetime.now(), total_amount, payment_method))
        
        order_id = cursor.lastrowid
        
        # 添加订单项目
        for item in items:
            cursor.execute('''
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES (?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['quantity'], item['price']))
            
            # 更新库存
            cursor.execute('''
            UPDATE products 
            SET stock = stock - ?
            WHERE id = ?
            ''', (item['quantity'], item['product_id']))
        
        self.conn.commit()
        return order_id

    def get_order(self, order_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT o.*, oi.*, p.model
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.id = ?
        ''', (order_id,))
        return cursor.fetchall()

    def get_all_orders(self):
        """
        获取所有订单
        返回: [(id, time, total_amount, payment_method), ...]
        """
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT id, datetime(order_time), total_amount, payment_method
        FROM orders
        ORDER BY order_time DESC
        ''')
        return cursor.fetchall()

    def get_order_details(self, order_id):
        """
        获取订单详情
        order_id: 订单ID
        返回: [{'model': str, 'price': float, 'quantity': int}, ...]
        """
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT p.model, oi.price, oi.quantity
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
        ''', (order_id,))
        
        details = []
        for row in cursor.fetchall():
            details.append({
                'model': row[0],
                'price': row[1],
                'quantity': row[2]
            })
        return details

    def get_low_stock_products(self, threshold=10):
        """
        获取库存低于阈值的商品
        threshold: 库存阈值
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM products WHERE stock <= ?', (threshold,))
        return cursor.fetchall()

    def search_products(self, keyword):
        """
        搜索商品（按条码或型号）
        """
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT * FROM products 
        WHERE barcode LIKE ? OR model LIKE ?
        ''', (f'%{keyword}%', f'%{keyword}%'))
        return cursor.fetchall()

    def get_sales_statistics(self, days=30):
        """
        获取销售统计数据
        days: 统计天数
        返回: {
            'total_sales': float,  # 总销售额
            'total_orders': int,   # 订单总数
            'popular_products': [], # 热销商品
            'daily_sales': []      # 每日销售额
        }
        """
        cursor = self.conn.cursor()
        start_date = datetime.now() - timedelta(days=days)
        
        # 总销售额和订单数
        cursor.execute('''
        SELECT COUNT(*) as order_count, SUM(total_amount) as total_sales
        FROM orders
        WHERE order_time >= ?
        ''', (start_date,))
        count_row = cursor.fetchone()
        
        # 热销商品
        cursor.execute('''
        SELECT p.model, SUM(oi.quantity) as total_quantity, 
               SUM(oi.quantity * oi.price) as total_amount
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.order_time >= ?
        GROUP BY p.id
        ORDER BY total_quantity DESC
        LIMIT 10
        ''', (start_date,))
        popular_products = cursor.fetchall()
        
        # 每日销售额
        cursor.execute('''
        SELECT date(order_time) as sale_date, 
               COUNT(*) as order_count,
               SUM(total_amount) as daily_sales
        FROM orders
        WHERE order_time >= ?
        GROUP BY date(order_time)
        ORDER BY sale_date
        ''', (start_date,))
        daily_sales = cursor.fetchall()
        
        return {
            'total_sales': count_row[1] or 0,
            'total_orders': count_row[0] or 0,
            'popular_products': popular_products,
            'daily_sales': daily_sales
        }

    # 商品分类管理
    def add_category(self, name, description=''):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO categories (name, description) VALUES (?, ?)',
                      (name, description))
        self.conn.commit()

    def get_all_categories(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM categories')
        return cursor.fetchall()

    def update_category(self, category_id, name=None, description=None):
        updates = []
        values = []
        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        
        if updates:
            values.append(category_id)
            cursor = self.conn.cursor()
            cursor.execute(f'''
            UPDATE categories 
            SET {", ".join(updates)}
            WHERE id = ?
            ''', values)
            self.conn.commit()

    # 会员管理
    def add_member(self, name, phone):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO members (name, phone, register_time)
        VALUES (?, ?, ?)
        ''', (name, phone, datetime.now()))
        self.conn.commit()

    def get_member_by_phone(self, phone):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM members WHERE phone = ?', (phone,))
        return cursor.fetchone()

    def update_member_points(self, member_id, points_delta):
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE members 
        SET points = points + ?,
            level = CASE 
                WHEN points + ? >= 10000 THEN 3
                WHEN points + ? >= 5000 THEN 2
                ELSE 1
            END
        WHERE id = ?
        ''', (points_delta, points_delta, points_delta, member_id))
        self.conn.commit()

    # 导入导出功能
    def export_products_to_csv(self, filename):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT p.barcode, p.model, p.price, p.stock, c.name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ''')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['条码', '型号', '价格', '库存', '分类'])
            writer.writerows(cursor.fetchall())

    def import_products_from_csv(self, filename):
        cursor = self.conn.cursor()
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 检查分类是否存在
                category_id = None
                if row.get('分类'):
                    cursor.execute('SELECT id FROM categories WHERE name = ?', 
                                 (row['分类'],))
                    result = cursor.fetchone()
                    if result:
                        category_id = result[0]
                    else:
                        cursor.execute('''
                        INSERT INTO categories (name) VALUES (?)
                        ''', (row['分类'],))
                        category_id = cursor.lastrowid

                # 添加或更新商品
                cursor.execute('''
                INSERT OR REPLACE INTO products 
                (barcode, model, price, stock, category_id)
                VALUES (?, ?, ?, ?, ?)
                ''', (row['条码'], row['型号'], float(row['价格']), 
                     int(row['库存']), category_id))
        
        self.conn.commit()

    def export_orders_to_csv(self, filename, start_date=None, end_date=None):
        cursor = self.conn.cursor()
        query = '''
        SELECT o.id, o.order_time, o.total_amount, o.payment_method,
               m.name as member_name, m.phone as member_phone,
               p.model, oi.quantity, oi.price
        FROM orders o
        LEFT JOIN members m ON o.member_id = m.id
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        '''
        params = []
        if start_date:
            query += ' WHERE o.order_time >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND o.order_time <= ?' if start_date else ' WHERE o.order_time <= ?'
            params.append(end_date)
        
        cursor.execute(query, params)
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['订单号', '时间', '总金额', '支付方式', 
                           '会员姓名', '会员电话', '商品', '数量', '单价'])
            writer.writerows(cursor.fetchall())

    def get_order_by_id(self, order_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, total_amount, payment_method, created_at
            FROM orders
            WHERE id = ?
        ''', (order_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'total_amount': row[1],
                'payment_method': row[2],
                'created_at': row[3]
            }
        return None

    def get_order_items(self, order_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.model, oi.quantity, oi.price
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (order_id,))
        items = []
        for row in cursor.fetchall():
            items.append({
                'model': row[0],
                'quantity': row[1],
                'price': row[2]
            })
        return items 