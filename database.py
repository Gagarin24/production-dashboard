import sqlite3
import pandas as pd
from datetime import datetime
import os
import time

class ProductionDB:
    def __init__(self, db_path='data/production.db'):
        os.makedirs('data', exist_ok=True)
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                short_name TEXT NOT NULL
            )
        ''')
        
        standard_units = [
            ('Штуки', 'шт'),
            ('Килограммы', 'кг'),
            ('Граммы', 'г'),
            ('Тонны', 'т'),
            ('Литры', 'л'),
            ('Миллилитры', 'мл'),
            ('Метры', 'м'),
            ('Сантиметры', 'см'),
            ('Квадратные метры', 'м²'),
            ('Кубические метры', 'м³'),
            ('Упаковки', 'упак'),
            ('Коробки', 'кор')
        ]
        
        for unit_name, short_name in standard_units:
            cursor.execute('''
                INSERT OR IGNORE INTO units (name, short_name) VALUES (?, ?)
            ''', (unit_name, short_name))
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL
            )
        ''')
        
        standard_categories = [
            ('Сырье', 'raw'),
            ('Полуфабрикаты', 'semifinished'),
            ('Готовая продукция', 'finished'),
            ('Расходные материалы', 'consumables')
        ]
        
        for cat_name, cat_type in standard_categories:
            cursor.execute('''
                INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)
            ''', (cat_name, cat_type))
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER,
                unit_id INTEGER,
                description TEXT,
                min_stock REAL DEFAULT 0,
                current_stock REAL DEFAULT 0,
                avg_cost REAL DEFAULT 0,
                selling_price REAL DEFAULT 0,
                created_date TEXT,
                FOREIGN KEY (category_id) REFERENCES categories (id),
                FOREIGN KEY (unit_id) REFERENCES units (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                position TEXT,
                hourly_rate REAL DEFAULT 0,
                created_date TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                movement_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price_per_unit REAL,
                total_cost REAL,
                employee_id INTEGER,
                notes TEXT,
                movement_date TEXT,
                created_date TEXT,
                FOREIGN KEY (product_id) REFERENCES products (id),
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_name TEXT,
                employee_id INTEGER,
                output_product_id INTEGER,
                output_quantity REAL,
                output_cost REAL,
                production_date TEXT,
                notes TEXT,
                created_date TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees (id),
                FOREIGN KEY (output_product_id) REFERENCES products (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_id INTEGER,
                product_id INTEGER,
                quantity_used REAL,
                cost REAL,
                FOREIGN KEY (production_id) REFERENCES production_operations (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                expense_date TEXT,
                created_date TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_units(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM units ORDER BY name", conn)
        conn.close()
        return df
    
    def get_categories(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM categories ORDER BY name", conn)
        conn.close()
        return df
    
    def add_category(self, name, cat_type):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO categories (name, type) VALUES (?, ?)
        ''', (name, cat_type))
        conn.commit()
        cat_id = cursor.lastrowid
        conn.close()
        return cat_id
    
    def add_product(self, product_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (
                name, category_id, unit_id, description, min_stock,
                current_stock, avg_cost, selling_price, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_data['name'],
            product_data['category_id'],
            product_data['unit_id'],
            product_data.get('description', ''),
            product_data.get('min_stock', 0),
            product_data.get('current_stock', 0),
            product_data.get('avg_cost', 0),
            product_data.get('selling_price', 0),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        return product_id
    
    def get_products(self):
        conn = self.get_connection()
        query = '''
            SELECT 
                p.*,
                c.name as category_name,
                u.short_name as unit_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN units u ON p.unit_id = u.id
            ORDER BY p.name
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def get_product_by_id(self, product_id):
        conn = self.get_connection()
        df = pd.read_sql_query(f"SELECT * FROM products WHERE id = {product_id}", conn)
        conn.close()
        return df.iloc[0] if not df.empty else None
    
    def update_product_stock(self, product_id, new_stock, new_avg_cost=None):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                if new_avg_cost is not None:
                    cursor.execute('''
                        UPDATE products SET current_stock = ?, avg_cost = ? WHERE id = ?
                    ''', (new_stock, new_avg_cost, product_id))
                else:
                    cursor.execute('''
                        UPDATE products SET current_stock = ? WHERE id = ?
                    ''', (new_stock, product_id))
                conn.commit()
                conn.close()
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(0.1)
                    continue
                else:
                    if 'conn' in locals():
                        conn.close()
                    raise
    
    def add_employee(self, employee_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO employees (name, position, hourly_rate, created_date)
            VALUES (?, ?, ?, ?)
        ''', (
            employee_data['name'],
            employee_data.get('position', ''),
            employee_data.get('hourly_rate', 0),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
        emp_id = cursor.lastrowid
        conn.close()
        return emp_id
    
    def get_employees(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM employees ORDER BY name", conn)
        conn.close()
        return df
    
    def add_stock_movement(self, movement_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO stock_movements (
                product_id, movement_type, quantity, price_per_unit,
                total_cost, employee_id, notes, movement_date, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            movement_data['product_id'],
            movement_data['movement_type'],
            movement_data['quantity'],
            movement_data.get('price_per_unit', 0),
            movement_data.get('total_cost', 0),
            movement_data.get('employee_id'),
            movement_data.get('notes', ''),
            movement_data.get('movement_date', datetime.now().strftime('%Y-%m-%d')),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        conn.commit()
        movement_id = cursor.lastrowid
        conn.close()
        
        product = self.get_product_by_id(movement_data['product_id'])
        current_stock = product['current_stock']
        
        if movement_data['movement_type'] == 'in':
            new_stock = current_stock + movement_data['quantity']
            if movement_data.get('price_per_unit', 0) > 0:
                old_value = current_stock * product['avg_cost']
                new_value = movement_data['quantity'] * movement_data['price_per_unit']
                new_avg_cost = (old_value + new_value) / new_stock if new_stock > 0 else 0
                self.update_product_stock(movement_data['product_id'], new_stock, new_avg_cost)
            else:
                self.update_product_stock(movement_data['product_id'], new_stock)
        else:
            new_stock = current_stock - movement_data['quantity']
            self.update_product_stock(movement_data['product_id'], new_stock)
        
        return movement_id
    
    def get_stock_movements(self, start_date=None, end_date=None):
        conn = self.get_connection()
        query = '''
            SELECT 
                sm.*,
                p.name as product_name,
                u.short_name as unit_name,
                e.name as employee_name
            FROM stock_movements sm
            LEFT JOIN products p ON sm.product_id = p.id
            LEFT JOIN units u ON p.unit_id = u.id
            LEFT JOIN employees e ON sm.employee_id = e.id
        '''
        
        if start_date and end_date:
            query += f" WHERE sm.movement_date BETWEEN '{start_date}' AND '{end_date}'"
        
        query += " ORDER BY sm.movement_date DESC, sm.created_date DESC"
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def add_production_operation(self, production_data, materials_used):
        time.sleep(0.1)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO production_operations (
                operation_name, employee_id, output_product_id,
                output_quantity, output_cost, production_date, notes, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            production_data['operation_name'],
            production_data.get('employee_id'),
            production_data['output_product_id'],
            production_data['output_quantity'],
            production_data['output_cost'],
            production_data.get('production_date', datetime.now().strftime('%Y-%m-%d')),
            production_data.get('notes', ''),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        production_id = cursor.lastrowid
        
        total_materials_cost = 0
        for material in materials_used:
            cursor.execute('''
                INSERT INTO production_materials (
                    production_id, product_id, quantity_used, cost
                ) VALUES (?, ?, ?, ?)
            ''', (
                production_id,
                material['product_id'],
                material['quantity_used'],
                material['cost']
            ))
            
            total_materials_cost += material['cost']
        
        conn.commit()
        conn.close()
        
        for material in materials_used:
            self.add_stock_movement({
                'product_id': material['product_id'],
                'movement_type': 'out',
                'quantity': material['quantity_used'],
                'notes': f"Использовано в производстве: {production_data['operation_name']}",
                'movement_date': production_data.get('production_date', datetime.now().strftime('%Y-%m-%d'))
            })
        
        cost_per_unit = (total_materials_cost + production_data['output_cost']) / production_data['output_quantity']
        
        self.add_stock_movement({
            'product_id': production_data['output_product_id'],
            'movement_type': 'in',
            'quantity': production_data['output_quantity'],
            'price_per_unit': cost_per_unit,
            'total_cost': total_materials_cost + production_data['output_cost'],
            'employee_id': production_data.get('employee_id'),
            'notes': f"Произведено: {production_data['operation_name']}",
            'movement_date': production_data.get('production_date', datetime.now().strftime('%Y-%m-%d'))
        })
        
        return production_id
    
    def get_production_operations(self, start_date=None, end_date=None):
        conn = self.get_connection()
        query = '''
            SELECT 
                po.*,
                p.name as output_product_name,
                u.short_name as output_unit,
                e.name as employee_name
            FROM production_operations po
            LEFT JOIN products p ON po.output_product_id = p.id
            LEFT JOIN units u ON p.unit_id = u.id
            LEFT JOIN employees e ON po.employee_id = e.id
        '''
        
        if start_date and end_date:
            query += f" WHERE po.production_date BETWEEN '{start_date}' AND '{end_date}'"
        
        query += " ORDER BY po.production_date DESC"
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    def delete_production_operation(self, production_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        operation = pd.read_sql_query(
            f"SELECT * FROM production_operations WHERE id = {production_id}", 
            conn
        )
        
        if operation.empty:
            conn.close()
            return {"success": False, "message": "Операция не найдена"}
        
        operation_row = operation.iloc[0]
        
        materials = pd.read_sql_query(
            f"SELECT * FROM production_materials WHERE production_id = {production_id}",
            conn
        )
        
        output_product_id = int(operation_row['output_product_id'])
        required_output = float(operation_row['output_quantity'])
        
        # Читаем текущие остатки из БД
        cursor.execute("SELECT current_stock FROM products WHERE id = ?", (output_product_id,))
        result = cursor.fetchone()
        
        if result is None:
            conn.close()
            return {"success": False, "message": f"Продукт с ID={output_product_id} не найден"}
        
        stock_before = float(result[0])
        
        print(f"DEBUG: Продукт ID={output_product_id}")
        print(f"DEBUG: Остаток ДО удаления: {stock_before}")
        print(f"DEBUG: Нужно списать: {required_output}")
        
        warning_message = None
        
        if stock_before < required_output:
            warning_message = f"На складе только {stock_before:.2f}, а нужно списать {required_output:.2f}. Будет списано всё, что есть."
        
        # ВОЗВРАЩАЕМ материалы
        for idx, material in materials.iterrows():
            mat_id = int(material['product_id'])
            mat_qty = float(material['quantity_used'])
            
            cursor.execute("SELECT current_stock FROM products WHERE id = ?", (mat_id,))
            mat_result = cursor.fetchone()
            
            if mat_result:
                current_mat_stock = float(mat_result[0])
                new_mat_stock = current_mat_stock + mat_qty
                
                cursor.execute('''
                    UPDATE products SET current_stock = ? WHERE id = ?
                ''', (new_mat_stock, mat_id))
                
                print(f"DEBUG: Материал {mat_id} возвращён: {current_mat_stock} + {mat_qty} = {new_mat_stock}")
        
        # СПИСЫВАЕМ готовую продукцию
        actual_removed = min(stock_before, required_output)
        new_output_stock = stock_before - actual_removed
        
        print(f"DEBUG: Списываем продукцию: {stock_before} - {actual_removed} = {new_output_stock}")
        
        cursor.execute('''
            UPDATE products SET current_stock = ? WHERE id = ?
        ''', (new_output_stock, output_product_id))
        
        # Удаляем записи
        cursor.execute('''
            DELETE FROM stock_movements 
            WHERE notes LIKE ?
        ''', (f"%{operation_row['operation_name']}%",))
        
        cursor.execute("DELETE FROM production_materials WHERE production_id=?", (production_id,))
        cursor.execute("DELETE FROM production_operations WHERE id=?", (production_id,))
        
        # КОММИТ всех изменений
        conn.commit()
        
        # Проверяем результат ПОСЛЕ коммита
        cursor.execute("SELECT current_stock FROM products WHERE id = ?", (output_product_id,))
        after_result = cursor.fetchone()
        stock_after = float(after_result[0]) if after_result else 0.0
        
        print(f"DEBUG: Остаток ПОСЛЕ обновления: {stock_after}")
        
        conn.close()
        
        return {
            "success": True, 
            "message": "Операция удалена", 
            "warning": warning_message,
            "materials_returned": len(materials),
            "output_removed": actual_removed,
            "debug_info": f"Было: {stock_before}, стало: {stock_after}"
        }
   
    def add_expense(self, expense_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expenses (
                category, description, amount, expense_date, created_date
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            expense_data['category'],
            expense_data.get('description', ''),
            expense_data['amount'],
            expense_data.get('expense_date', datetime.now().strftime('%Y-%m-%d')),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
        expense_id = cursor.lastrowid
        conn.close()
        return expense_id
    
    def get_expenses(self, start_date=None, end_date=None):
        conn = self.get_connection()
        query = "SELECT * FROM expenses"
        
        if start_date and end_date:
            query += f" WHERE expense_date BETWEEN '{start_date}' AND '{end_date}'"
        
        query += " ORDER BY expense_date DESC"
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
