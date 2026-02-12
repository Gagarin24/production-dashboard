import psycopg2
import pandas as pd
from datetime import datetime
import bcrypt
import os

class ProductionDB:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv('DATABASE_URL')
        self.init_database()
    
    def get_connection(self):
        return psycopg2.connect(self.db_url)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица компаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                login VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS units (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                short_name VARCHAR(20) NOT NULL
            )
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM units")
        if cursor.fetchone()[0] == 0:
            standard_units = [
                ('Штуки', 'шт'), ('Килограммы', 'кг'), ('Граммы', 'г'),
                ('Тонны', 'т'), ('Литры', 'л'), ('Миллилитры', 'мл'),
                ('Метры', 'м'), ('Сантиметры', 'см'), ('Квадратные метры', 'м²'),
                ('Кубические метры', 'м³'), ('Упаковки', 'упак'), ('Коробки', 'кор')
            ]
            cursor.executemany('INSERT INTO units (name, short_name) VALUES (%s, %s)', standard_units)
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                type VARCHAR(50) NOT NULL
            )
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            standard_categories = [
                ('Сырье', 'raw'), ('Полуфабрикаты', 'semifinished'),
                ('Готовая продукция', 'finished'), ('Расходные материалы', 'consumables')
            ]
            cursor.executemany('INSERT INTO categories (name, type) VALUES (%s, %s)', standard_categories)
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                category_id INTEGER REFERENCES categories(id),
                unit_id INTEGER REFERENCES units(id),
                description TEXT,
                min_stock DECIMAL(10,2) DEFAULT 0,
                current_stock DECIMAL(10,2) DEFAULT 0,
                avg_cost DECIMAL(10,2) DEFAULT 0,
                selling_price DECIMAL(10,2) DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                position VARCHAR(100),
                hourly_rate DECIMAL(10,2) DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_movements (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                movement_type VARCHAR(10) NOT NULL,
                quantity DECIMAL(10,2) NOT NULL,
                price_per_unit DECIMAL(10,2),
                total_cost DECIMAL(10,2),
                employee_id INTEGER REFERENCES employees(id),
                notes TEXT,
                movement_date DATE,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_operations (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                operation_name VARCHAR(255),
                employee_id INTEGER REFERENCES employees(id),
                output_product_id INTEGER REFERENCES products(id),
                output_quantity DECIMAL(10,2),
                output_cost DECIMAL(10,2),
                production_date DATE,
                notes TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_materials (
                id SERIAL PRIMARY KEY,
                production_id INTEGER REFERENCES production_operations(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                quantity_used DECIMAL(10,2),
                cost DECIMAL(10,2)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                category VARCHAR(100) NOT NULL,
                description TEXT,
                amount DECIMAL(10,2) NOT NULL,
                expense_date DATE,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ===== АВТОРИЗАЦИЯ =====
    def register_user(self, company_name, login, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO companies (name) VALUES (%s) RETURNING id', (company_name,))
            company_id = cursor.fetchone()[0]
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute('INSERT INTO users (company_id, login, password_hash) VALUES (%s, %s, %s)',
                         (company_id, login, password_hash))
            conn.commit()
            conn.close()
            return {"success": True, "company_id": company_id}
        except psycopg2.errors.UniqueViolation:
            conn.close()
            return {"success": False, "message": "Логин уже занят"}
        except Exception as e:
            conn.close()
            return {"success": False, "message": str(e)}
    
    def login_user(self, login, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, company_id, password_hash FROM users WHERE login = %s', (login,))
        result = cursor.fetchone()
        conn.close()
        if result is None:
            return {"success": False, "message": "Неверный логин или пароль"}
        user_id, company_id, password_hash = result
        if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            return {"success": True, "user_id": user_id, "company_id": company_id}
        else:
            return {"success": False, "message": "Неверный логин или пароль"}
    
    def get_company_name(self, company_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM companies WHERE id = %s', (company_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Неизвестная компания"
    
    # ===== СПРАВОЧНИКИ =====
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
    
    # ===== ПРОДУКТЫ =====
    def add_product(self, company_id, product_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (company_id, name, category_id, unit_id, description, min_stock,
                current_stock, avg_cost, selling_price) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (company_id, product_data['name'], product_data['category_id'], product_data['unit_id'],
              product_data.get('description', ''), product_data.get('min_stock', 0),
              product_data.get('current_stock', 0), product_data.get('avg_cost', 0),
              product_data.get('selling_price', 0)))
        product_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return product_id
    
    def get_products(self, company_id):
        conn = self.get_connection()
        query = '''
            SELECT p.*, c.name as category_name, u.short_name as unit_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN units u ON p.unit_id = u.id
            WHERE p.company_id = %s ORDER BY p.name
        '''
        df = pd.read_sql_query(query, conn, params=(company_id,))
        conn.close()
        return df
    
    def get_product_by_id(self, product_id):
        conn = self.get_connection()
        query = '''
            SELECT p.*, c.name as category_name, u.short_name as unit_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN units u ON p.unit_id = u.id
            WHERE p.id = %s
        '''
        df = pd.read_sql_query(query, conn, params=(product_id,))
        conn.close()
        return df.iloc[0] if not df.empty else None
    
    def update_product_stock(self, product_id, new_stock, new_avg_cost=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if new_avg_cost is not None:
            cursor.execute('UPDATE products SET current_stock = %s, avg_cost = %s WHERE id = %s',
                         (new_stock, new_avg_cost, product_id))
        else:
            cursor.execute('UPDATE products SET current_stock = %s WHERE id = %s', (new_stock, product_id))
        conn.commit()
        conn.close()
    
    # ===== СОТРУДНИКИ =====
    def add_employee(self, company_id, employee_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO employees (company_id, name, position, hourly_rate) VALUES (%s, %s, %s, %s) RETURNING id
        ''', (company_id, employee_data['name'], employee_data.get('position', ''),
              employee_data.get('hourly_rate', 0)))
        emp_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return emp_id
    
    def get_employees(self, company_id):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM employees WHERE company_id = %s ORDER BY name",
                              conn, params=(company_id,))
        conn.close()
        return df
    
    # ===== ДВИЖЕНИЕ ТОВАРОВ =====
    def add_stock_movement(self, company_id, movement_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stock_movements (company_id, product_id, movement_type, quantity, price_per_unit,
                total_cost, employee_id, notes, movement_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (company_id, movement_data['product_id'], movement_data['movement_type'],
              movement_data['quantity'], movement_data.get('price_per_unit', 0),
              movement_data.get('total_cost', 0), movement_data.get('employee_id'),
              movement_data.get('notes', ''), movement_data.get('movement_date', datetime.now().date())))
        movement_id = cursor.fetchone()[0]
        conn.commit()
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
    
    def get_stock_movements(self, company_id, start_date=None, end_date=None):
        conn = self.get_connection()
        query = '''
            SELECT sm.*, p.name as product_name, u.short_name as unit_name, e.name as employee_name
            FROM stock_movements sm
            LEFT JOIN products p ON sm.product_id = p.id
            LEFT JOIN units u ON p.unit_id = u.id
            LEFT JOIN employees e ON sm.employee_id = e.id
            WHERE sm.company_id = %s
        '''
        params = [company_id]
        if start_date:
            query += ' AND sm.movement_date >= %s'
            params.append(start_date)
        if end_date:
            query += ' AND sm.movement_date <= %s'
            params.append(end_date)
        query += ' ORDER BY sm.movement_date DESC'
        df = pd.read_sql_query(query, conn, params=tuple(params))
        conn.close()
        return df
    
    # ===== ПРОИЗВОДСТВО =====
    def add_production_operation(self, company_id, production_data, materials_used):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO production_operations (company_id, operation_name, employee_id, output_product_id,
                output_quantity, output_cost, production_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (company_id, production_data['operation_name'], production_data.get('employee_id'),
              production_data['output_product_id'], production_data['output_quantity'],
              production_data['output_cost'], production_data.get('production_date', datetime.now().date()),
              production_data.get('notes', '')))
        production_id = cursor.fetchone()[0]
        
        for material in materials_used:
            cursor.execute('''
                INSERT INTO production_materials (production_id, product_id, quantity_used, cost)
                VALUES (%s, %s, %s, %s)
            ''', (production_id, material['product_id'], material['quantity_used'], material['cost']))
            product = self.get_product_by_id(material['product_id'])
            new_stock = product['current_stock'] - material['quantity_used']
            self.update_product_stock(material['product_id'], new_stock)
        
        output_product = self.get_product_by_id(production_data['output_product_id'])
        new_output_stock = output_product['current_stock'] + production_data['output_quantity']
        cost_per_unit = production_data['output_cost'] / production_data['output_quantity']
        old_value = output_product['current_stock'] * output_product['avg_cost']
        new_value = production_data['output_quantity'] * cost_per_unit
        new_avg_cost = (old_value + new_value) / new_output_stock if new_output_stock > 0 else cost_per_unit
        self.update_product_stock(production_data['output_product_id'], new_output_stock, new_avg_cost)
        
        conn.commit()
        conn.close()
        return production_id
    
    def get_production_operations(self, company_id, start_date=None, end_date=None):
        conn = self.get_connection()
        query = '''
            SELECT 
                po.id, 
                po.company_id, 
                po.operation_name, 
                po.employee_id, 
                po.output_product_id, 
                po.output_quantity, 
                po.output_cost, 
                CAST(po.production_date AS TEXT) as production_date,
                po.notes, 
                po.created_date,
                COALESCE(p.name, 'Неизвестно') as output_product_name, 
                COALESCE(u.short_name, '') as output_unit, 
                COALESCE(e.name, 'Не указан') as employee_name
            FROM production_operations po
            LEFT JOIN products p ON po.output_product_id = p.id
            LEFT JOIN units u ON p.unit_id = u.id
            LEFT JOIN employees e ON po.employee_id = e.id
            WHERE po.company_id = %s
        '''
        params = [company_id]
        if start_date:
            query += ' AND po.production_date >= %s'
            params.append(start_date)
        if end_date:
            query += ' AND po.production_date <= %s'
            params.append(end_date)
        query += ' ORDER BY po.production_date DESC'
        df = pd.read_sql_query(query, conn, params=tuple(params))
        conn.close()
        return df
    
    def delete_production_operation(self, production_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем данные операции
        cursor.execute("""
            SELECT id, company_id, operation_name, employee_id, output_product_id, 
                   output_quantity, output_cost, production_date, notes
            FROM production_operations 
            WHERE id = %s
        """, (production_id,))
        operation = cursor.fetchone()
        
        if not operation:
            conn.close()
            return {"success": False, "message": "Операция не найдена"}
        
        # Распаковываем данные
        op_id, company_id, op_name, employee_id, output_product_id, output_quantity, output_cost, prod_date, notes = operation
        
        # Получаем материалы
        cursor.execute("""
            SELECT id, production_id, product_id, quantity_used, cost
            FROM production_materials 
            WHERE production_id = %s
        """, (production_id,))
        materials = cursor.fetchall()
        
        # Возвращаем материалы на склад
        for material in materials:
            mat_id, prod_id, product_id, quantity_used, cost = material
            cursor.execute("SELECT current_stock FROM products WHERE id = %s", (product_id,))
            result = cursor.fetchone()
            if result:
                current_stock = result[0]
                new_stock = current_stock + quantity_used
                cursor.execute("UPDATE products SET current_stock = %s WHERE id = %s", (new_stock, product_id))
        
        # Списываем готовую продукцию
        cursor.execute("SELECT current_stock FROM products WHERE id = %s", (output_product_id,))
        result = cursor.fetchone()
        if result:
            current_output = result[0]
            new_output = max(0, current_output - output_quantity)
            cursor.execute("UPDATE products SET current_stock = %s WHERE id = %s", (new_output, output_product_id))
            actual_removed = min(current_output, output_quantity)
        else:
            actual_removed = 0
        
        # Удаляем записи
        cursor.execute("DELETE FROM production_materials WHERE production_id = %s", (production_id,))
        cursor.execute("DELETE FROM production_operations WHERE id = %s", (production_id,))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True, 
            "materials_returned": len(materials), 
            "output_removed": actual_removed
        }
    
    # ===== РАСХОДЫ =====
    def add_expense(self, company_id, expense_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expenses (company_id, category, description, amount, expense_date)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (company_id, expense_data['category'], expense_data.get('description', ''),
              expense_data['amount'], expense_data.get('expense_date', datetime.now().date())))
        expense_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return expense_id
    
    def get_expenses(self, company_id, start_date=None, end_date=None):
        conn = self.get_connection()
        query = "SELECT * FROM expenses WHERE company_id = %s"
        params = [company_id]
        if start_date:
            query += " AND expense_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND expense_date <= %s"
            params.append(end_date)
        query += " ORDER BY expense_date DESC"
        df = pd.read_sql_query(query, conn, params=tuple(params))
        conn.close()
        return df
