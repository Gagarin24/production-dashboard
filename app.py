import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import ProductionDB
from datetime import datetime, timedelta
import time
import os

st.set_page_config(page_title="Производственный дашборд", page_icon="🏭", layout="wide")

# Инициализация БД
@st.cache_resource
def init_db():
    db_url = os.getenv('DATABASE_URL') or st.secrets.get("database", {}).get("url")
    return ProductionDB(db_url)

db = init_db()

# ===== СТРАНИЦА АВТОРИЗАЦИИ =====
def auth_page():
    st.title("🔐 Вход в систему")
    
    tab1, tab2 = st.tabs(["🔑 Вход", "📝 Регистрация"])
    
    with tab1:
        st.subheader("Войти в существующий аккаунт")
        with st.form("login_form"):
            login = st.text_input("Логин (email)", placeholder="your@email.com")
            password = st.text_input("Пароль", type="password")
            submit = st.form_submit_button("🔓 Войти", use_container_width=True)
            
            if submit:
                if not login or not password:
                    st.error("⚠️ Заполните все поля!")
                else:
                    result = db.login_user(login, password)
                    if result["success"]:
                        st.session_state.authenticated = True
                        st.session_state.user_id = result["user_id"]
                        st.session_state.company_id = result["company_id"]
                        st.session_state.company_name = db.get_company_name(result["company_id"])
                        st.success(f"✅ Добро пожаловать, {st.session_state.company_name}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {result['message']}")
    
    with tab2:
        st.subheader("Создать новый аккаунт")
        with st.form("register_form"):
            company_name = st.text_input("Название компании", placeholder="ООО 'Производство'")
            new_login = st.text_input("Логин (email)", placeholder="your@email.com", key="reg_login")
            new_password = st.text_input("Пароль", type="password", key="reg_password")
            new_password2 = st.text_input("Повторите пароль", type="password")
            submit_reg = st.form_submit_button("📝 Зарегистрироваться", use_container_width=True)
            
            if submit_reg:
                if not company_name or not new_login or not new_password:
                    st.error("⚠️ Заполните все поля!")
                elif new_password != new_password2:
                    st.error("⚠️ Пароли не совпадают!")
                elif len(new_password) < 6:
                    st.error("⚠️ Пароль должен быть не менее 6 символов!")
                else:
                    result = db.register_user(company_name, new_login, new_password)
                    if result["success"]:
                        st.success("✅ Регистрация успешна! Теперь войдите в систему.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ {result['message']}")

# ===== ПРОВЕРКА АВТОРИЗАЦИИ =====
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    auth_page()
    st.stop()

# ===== ГЛАВНАЯ ЧАСТЬ ДАШБОРДА =====
company_id = st.session_state.company_id
company_name = st.session_state.company_name

st.title(f"🏭 {company_name}")
st.sidebar.title("Навигация")
st.sidebar.info(f"👤 **Компания:** {company_name}")

if st.sidebar.button("🚪 Выйти", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()

page = st.sidebar.radio("Выберите раздел:", [
    "📊 Обзор", "📦 Склад", "🏭 Производство", 
    "💰 Расходы", "📈 Аналитика", "⚙️ Настройки"
])

# ===== СТРАНИЦА: ОБЗОР =====
if page == "📊 Обзор":
    st.header("📊 Общий обзор")
    
    products_df = db.get_products(company_id)
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    movements_week = db.get_stock_movements(company_id, week_ago.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    expenses_month = db.get_expenses(company_id, month_ago.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    production_month = db.get_production_operations(company_id, month_ago.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📦 Позиций на складе", len(products_df))
    
    with col2:
        total_value = (products_df['current_stock'] * products_df['avg_cost']).sum()
        st.metric("💰 Стоимость запасов", f"{total_value:,.2f} ₽")
    
    with col3:
        total_expenses = expenses_month['amount'].sum() if not expenses_month.empty else 0
        st.metric("💸 Расходы (месяц)", f"{total_expenses:,.2f} ₽")
    
    with col4:
        production_count = len(production_month)
        st.metric("🏭 Операций (месяц)", production_count)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 Текущие запасы")
        if not products_df.empty:
            display_df = products_df[['name', 'current_stock', 'unit_short', 'avg_cost']].copy()
            display_df['Стоимость'] = display_df['current_stock'] * display_df['avg_cost']
            display_df = display_df.rename(columns={
                'name': 'Продукт',
                'current_stock': 'Остаток',
                'unit_short': 'Ед.',
                'avg_cost': 'Цена',
                'Стоимость': 'Всего ₽'
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("📭 Нет продуктов на складе")
    
    with col2:
        st.subheader("⚠️ Низкие остатки")
        low_stock = products_df[products_df['current_stock'] < products_df['min_stock']]
        if not low_stock.empty:
            display_low = low_stock[['name', 'current_stock', 'min_stock', 'unit_short']].rename(columns={
                'name': 'Продукт',
                'current_stock': 'Текущий',
                'min_stock': 'Минимум',
                'unit_short': 'Ед.'
            })
            st.dataframe(display_low, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Все запасы в норме")
    
    st.markdown("---")
    st.subheader("📋 Последние движения (неделя)")
    if not movements_week.empty:
        display_movements = movements_week[['movement_date', 'movement_type', 'product_name', 'quantity', 'unit_name', 'employee_name']].copy()
        display_movements['movement_type'] = display_movements['movement_type'].map({'in': '➕ Приход', 'out': '➖ Расход'})
        display_movements = display_movements.rename(columns={
            'movement_date': 'Дата',
            'movement_type': 'Тип',
            'product_name': 'Продукт',
            'quantity': 'Количество',
            'unit_name': 'Ед.',
            'employee_name': 'Сотрудник'
        })
        st.dataframe(display_movements, use_container_width=True, hide_index=True)
    else:
        st.info("📭 Нет движений за последнюю неделю")

# ===== СТРАНИЦА: СКЛАД =====
elif page == "📦 Склад":
    st.header("📦 Управление складом")
    
    tab1, tab2, tab3 = st.tabs(["📋 Остатки", "➕ Приход товара", "➖ Расход товара"])
    
    with tab1:
        st.subheader("📋 Текущие остатки")
        products_df = db.get_products(company_id)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            categories = db.get_categories()
            selected_category = st.selectbox("Фильтр по категории", ["Все"] + categories['name'].tolist())
        with col2:
            show_zero = st.checkbox("Показать нулевые остатки", value=True)
        
        if not products_df.empty:
            if selected_category != "Все":
                products_df = products_df[products_df['category_name'] == selected_category]
            if not show_zero:
                products_df = products_df[products_df['current_stock'] > 0]
            
            products_df['Стоимость'] = products_df['current_stock'] * products_df['avg_cost']
            display_df = products_df[['name', 'category_name', 'current_stock', 'unit_short', 'avg_cost', 'Стоимость']].rename(columns={
                'name': 'Продукт',
                'category_name': 'Категория',
                'current_stock': 'Остаток',
                'unit_short': 'Ед.',
                'avg_cost': 'Себест. ₽',
                'Стоимость': 'Всего ₽'
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            total_value = products_df['Стоимость'].sum()
            st.metric("💰 Общая стоимость запасов", f"{total_value:,.2f} ₽")
        else:
            st.info("📭 Нет продуктов на складе. Добавьте их в разделе 'Настройки'.")
    
    with tab2:
        st.subheader("➕ Приход товара на склад")
        products_df = db.get_products(company_id)
        employees_df = db.get_employees(company_id)
        
        if products_df.empty:
            st.warning("⚠️ Сначала добавьте продукты в разделе 'Настройки → Продукты'")
        else:
            with st.form("stock_in_form"):
                col1, col2 = st.columns(2)
                with col1:
                    product_id = st.selectbox("Продукт*", products_df['id'], 
                                            format_func=lambda x: products_df[products_df['id']==x]['name'].values[0])
                    quantity = st.number_input("Количество*", min_value=0.01, value=1.0, step=0.1)
                    price = st.number_input("Цена за единицу ₽*", min_value=0.0, value=0.0, step=10.0)
                
                with col2:
                    movement_date = st.date_input("Дата прихода", value=datetime.now().date())
                    employee_id = st.selectbox("Сотрудник", [None] + employees_df['id'].tolist(),
                                              format_func=lambda x: "Не указан" if x is None else employees_df[employees_df['id']==x]['name'].values[0])
                    notes = st.text_area("Примечание", placeholder="Опционально")
                
                submit = st.form_submit_button("➕ Добавить приход", use_container_width=True)
                
                if submit:
                    if quantity <= 0:
                        st.error("⚠️ Количество должно быть больше нуля!")
                    else:
                        movement_data = {
                            'product_id': product_id,
                            'movement_type': 'in',
                            'quantity': quantity,
                            'price_per_unit': price,
                            'total_cost': quantity * price,
                            'employee_id': employee_id,
                            'notes': notes,
                            'movement_date': movement_date
                        }
                        db.add_stock_movement(company_id, movement_data)
                        st.success("✅ Приход товара зафиксирован!")
                        time.sleep(1)
                        st.rerun()
    
    with tab3:
        st.subheader("➖ Расход товара со склада")
        products_df = db.get_products(company_id)
        employees_df = db.get_employees(company_id)
        
        if products_df.empty:
            st.warning("⚠️ Нет продуктов на складе")
        else:
            available_products = products_df[products_df['current_stock'] > 0]
            if available_products.empty:
                st.warning("⚠️ Нет товаров с ненулевым остатком")
            else:
                with st.form("stock_out_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        product_id = st.selectbox("Продукт*", available_products['id'],
                                                format_func=lambda x: f"{available_products[available_products['id']==x]['name'].values[0]} (остаток: {available_products[available_products['id']==x]['current_stock'].values[0]} {available_products[available_products['id']==x]['unit_short'].values[0]})")
                        selected_product = available_products[available_products['id']==product_id].iloc[0]
                        max_quantity = selected_product['current_stock']
                        quantity = st.number_input(f"Количество* (макс: {max_quantity})", min_value=0.01, max_value=float(max_quantity), value=min(1.0, float(max_quantity)), step=0.1)
                    
                    with col2:
                        movement_date = st.date_input("Дата расхода", value=datetime.now().date())
                        employee_id = st.selectbox("Сотрудник", [None] + employees_df['id'].tolist(),
                                                  format_func=lambda x: "Не указан" if x is None else employees_df[employees_df['id']==x]['name'].values[0])
                        notes = st.text_area("Причина расхода", placeholder="Например: продажа, списание, брак")
                    
                    submit = st.form_submit_button("➖ Списать товар", use_container_width=True)
                    
                    if submit:
                        if quantity > max_quantity:
                            st.error(f"⚠️ Недостаточно товара на складе! Доступно: {max_quantity}")
                        else:
                            movement_data = {
                                'product_id': product_id,
                                'movement_type': 'out',
                                'quantity': quantity,
                                'price_per_unit': 0,
                                'total_cost': 0,
                                'employee_id': employee_id,
                                'notes': notes,
                                'movement_date': movement_date
                            }
                            db.add_stock_movement(company_id, movement_data)
                            st.success("✅ Расход товара зафиксирован!")
                            time.sleep(1)
                            st.rerun()

# ===== СТРАНИЦА: ПРОИЗВОДСТВО =====
elif page == "🏭 Производство":
    st.header("🏭 Управление производством")
    
    tab1, tab2 = st.tabs(["➕ Новая операция", "📋 История производства"])
    
    with tab1:
        st.subheader("➕ Создать производственную операцию")
        products_df = db.get_products(company_id)
        employees_df = db.get_employees(company_id)
        
        if products_df.empty:
            st.warning("⚠️ Сначала добавьте продукты")
        else:
            if 'materials_count' not in st.session_state:
                st.session_state.materials_count = 1
            
            with st.form("production_form"):
                col1, col2 = st.columns(2)
                with col1:
                    operation_name = st.text_input("Название операции*", placeholder="Производство досок")
                    operation_date = st.date_input("Дата операции", value=datetime.now().date())
                    employee_id = st.selectbox("Ответственный сотрудник", [None] + employees_df['id'].tolist(),
                                              format_func=lambda x: "Не указан" if x is None else employees_df[employees_df['id']==x]['name'].values[0])
                
                with col2:
                    additional_costs = st.number_input("Дополнительные расходы ₽", min_value=0.0, value=0.0, step=100.0,
                                                      help="Электричество, амортизация и т.д.")
                
                st.markdown("---")
                st.subheader("📦 Использованные материалы")
                
                materials_data = []
                total_material_cost = 0
                
                available_materials = products_df[products_df['current_stock'] > 0]
                if available_materials.empty:
                    st.warning("⚠️ Нет материалов с ненулевым остатком")
                else:
                    for i in range(st.session_state.materials_count):
                        st.markdown(f"**Материал #{i+1}**")
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            mat_id = st.selectbox(f"Продукт", available_materials['id'], key=f"mat_{i}",
                                                format_func=lambda x: f"{available_materials[available_materials['id']==x]['name'].values[0]} ({available_materials[available_materials['id']==x]['current_stock'].values[0]} {available_materials[available_materials['id']==x]['unit_short'].values[0]})")
                        with col2:
                            mat_product = available_materials[available_materials['id']==mat_id].iloc[0]
                            max_qty = mat_product['current_stock']
                            mat_qty = st.number_input(f"Количество (макс: {max_qty})", min_value=0.01, max_value=float(max_qty), value=min(1.0, float(max_qty)), step=0.1, key=f"qty_{i}")
                        with col3:
                            mat_cost = st.number_input("Цена ₽/ед", value=float(mat_product['avg_cost']), step=10.0, key=f"cost_{i}")
                        
                        materials_data.append({'product_id': mat_id, 'quantity_used': mat_qty, 'cost_per_unit': mat_cost})
                        total_material_cost += mat_qty * mat_cost
                        st.markdown("---")
                
                st.markdown("---")
                st.subheader("✅ Произведённая продукция")
                
                col1, col2 = st.columns(2)
                with col1:
                    output_product_id = st.selectbox("Готовая продукция*", products_df['id'],
                                                    format_func=lambda x: products_df[products_df['id']==x]['name'].values[0])
                with col2:
                    output_quantity = st.number_input("Количество произведённого*", min_value=0.01, value=1.0, step=0.1)
                
                total_cost = total_material_cost + additional_costs
                cost_per_unit = total_cost / output_quantity if output_quantity > 0 else 0
                
                st.info(f"""
                **💰 Расчёт себестоимости:**
                - Материалы: {total_material_cost:.2f} ₽
                - Доп. расходы: {additional_costs:.2f} ₽
                - **Итого:** {total_cost:.2f} ₽
                - **Себестоимость единицы:** {cost_per_unit:.2f} ₽
                """)
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("✅ Создать операцию", use_container_width=True)
                with col2:
                    if st.form_submit_button("➕ Добавить материал"):
                        st.session_state.materials_count += 1
                        st.rerun()
                
                if submit:
                    if not operation_name:
                        st.error("⚠️ Укажите название операции!")
                    elif not materials_data:
                        st.error("⚠️ Добавьте хотя бы один материал!")
                    elif output_quantity <= 0:
                        st.error("⚠️ Количество произведённого должно быть больше нуля!")
                    else:
                        production_data = {
                            'operation_name': operation_name,
                            'output_product_id': output_product_id,
                            'output_quantity': output_quantity,
                            'output_cost': total_cost,
                            'additional_costs': additional_costs,
                            'employee_id': employee_id,
                            'operation_date': operation_date
                        }
                        
                        try:
                            db.add_production_operation(company_id, production_data, materials_data)
                            st.success("🎉 **ПРОИЗВОДСТВЕННАЯ ОПЕРАЦИЯ УСПЕШНО СОЗДАНА!**")
                            st.balloons()
                            output_unit = products_df[products_df['id']==output_product_id]['unit_short'].values[0]
                            st.info(f"""
                            **📋 Детали операции:**
                            - Операция: {operation_name}
                            - Произведено: {output_quantity:.2f} {output_unit}
                            - Себестоимость: {cost_per_unit:.2f} ₽/ед
                            - Общие затраты: {total_cost:.2f} ₽
                            """)
                            st.session_state.materials_count = 1
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Ошибка: {str(e)}")
    
    with tab2:
        st.subheader("📋 История производственных операций")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("От", value=datetime.now().date() - timedelta(days=30))
        with col2:
            end_date = st.date_input("До", value=datetime.now().date())
        
        operations_df = db.get_production_operations(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
        if not operations_df.empty:
            operations_df['cost_per_unit'] = operations_df['output_cost'] / operations_df['output_quantity']
            
            for idx, row in operations_df.iterrows():
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                with col1:
                    st.write(f"**📅 {row['operation_date']}**")
                    st.write(f"🏭 {row['operation_name']}")
                with col2:
                    st.write(f"**👤 Сотрудник:**")
                    st.write(row['employee_name'] if row['employee_name'] else "Не указан")
                with col3:
                    st.write(f"**📦 Продукт:**")
                    st.write(f"{row['output_product_name']} ({row['output_quantity']:.2f} {row['output_unit']})")
                with col4:
                    st.write(f"**💰 Затраты:**")
                    st.write(f"{row['output_cost']:.2f} ₽")
                    st.write(f"({row['cost_per_unit']:.2f} ₽/ед)")
                
                if st.button(f"🗑️ Удалить", key=f"del_{row['id']}"):
                    result = db.delete_production_operation(row['id'])
                    if result["success"]:
                        st.success("✅ Операция удалена!")
                        st.info(f"♻️ Материалов возвращено: {result['materials_returned']}, готовой продукции списано: {result['output_removed']:.2f} {row['output_unit']}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {result['message']}")
                
                st.markdown("---")
            
            st.markdown("### 📊 Общая статистика")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Операций", len(operations_df))
            with col2:
                st.metric("Произведено единиц", f"{operations_df['output_quantity'].sum():.2f}")
            with col3:
                st.metric("Общие затраты", f"{operations_df['output_cost'].sum():,.2f} ₽")
        else:
            st.info("📭 Нет производственных операций за выбранный период")

# ===== СТРАНИЦА: РАСХОДЫ =====
elif page == "💰 Расходы":
    st.header("💰 Управление расходами")
    
    tab1, tab2 = st.tabs(["➕ Добавить расход", "📋 История расходов"])
    
    with tab1:
        st.subheader("➕ Добавить новый расход")
        
        with st.form("expense_form"):
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox("Категория*", [
                    "Зарплата", "Аренда", "Коммунальные услуги", "Транспорт",
                    "Реклама", "Налоги", "Обслуживание оборудования", "Прочее"
                ])
                amount = st.number_input("Сумма ₽*", min_value=0.0, value=0.0, step=100.0)
            
            with col2:
                expense_date = st.date_input("Дата расхода", value=datetime.now().date())
                description = st.text_area("Описание", placeholder="Детали расхода")
            
            submit = st.form_submit_button("➕ Добавить расход", use_container_width=True)
            
            if submit:
                if amount <= 0:
                    st.error("⚠️ Сумма должна быть больше нуля!")
                else:
                    expense_data = {
                        'category': category,
                        'amount': amount,
                        'description': description,
                        'expense_date': expense_date
                    }
                    db.add_expense(company_id, expense_data)
                    st.success("✅ Расход добавлен!")
                    time.sleep(1)
                    st.rerun()
    
    with tab2:
        st.subheader("📋 История расходов")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("От", value=datetime.now().date() - timedelta(days=30), key="exp_start")
        with col2:
            end_date = st.date_input("До", value=datetime.now().date(), key="exp_end")
        
        expenses_df = db.get_expenses(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
        if not expenses_df.empty:
            display_df = expenses_df[['expense_date', 'category', 'amount', 'description']].rename(columns={
                'expense_date': 'Дата',
                'category': 'Категория',
                'amount': 'Сумма ₽',
                'description': 'Описание'
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("📊 Расходы по категориям")
            
            category_totals = expenses_df.groupby('category')['amount'].sum().reset_index()
            fig = px.pie(category_totals, values='amount', names='category', title='Структура расходов')
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Общая сумма", f"{expenses_df['amount'].sum():,.2f} ₽")
            with col2:
                st.metric("Средний расход", f"{expenses_df['amount'].mean():,.2f} ₽")
            with col3:
                st.metric("Максимальный расход", f"{expenses_df['amount'].max():,.2f} ₽")
        else:
            st.info("📭 Нет расходов за выбранный период")

# ===== СТРАНИЦА: АНАЛИТИКА =====
elif page == "📈 Аналитика":
    st.header("📈 Аналитика и отчёты")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("От", value=datetime.now().date() - timedelta(days=30), key="analytics_start")
    with col2:
        end_date = st.date_input("До", value=datetime.now().date(), key="analytics_end")
    
    movements_df = db.get_stock_movements(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    production_df = db.get_production_operations(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    expenses_df = db.get_expenses(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    products_df = db.get_products(company_id)
    
    st.subheader("📊 Динамика движения товаров")
    if not movements_df.empty:
        movements_by_date = movements_df.groupby(['movement_date', 'movement_type']).size().reset_index(name='quantity')
        movements_by_date['Тип'] = movements_by_date['movement_type'].map({'in': '➕ Приход', 'out': '➖ Расход'})
        
        fig = px.line(movements_by_date, x='movement_date', y='quantity', color='Тип',
                     labels={'movement_date': 'Дата', 'quantity': 'Количество операций'},
                     color_discrete_map={'➕ Приход': '#00CC66', '➖ Расход': '#FF3333'},
                     markers=True)
        fig.update_layout(xaxis_title='Дата', yaxis_title='Количество операций', 
                         legend_title='Тип движения', hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 Нет данных о движении товаров за выбранный период")
    
    st.markdown("---")
    st.subheader("🏭 Производительность по сотрудникам")
    if not production_df.empty:
        emp_stats = production_df.groupby('employee_name').agg({
            'id': 'count',
            'output_quantity': 'sum',
            'output_cost': 'sum'
        }).reset_index()
        emp_stats.columns = ['Сотрудник', 'Операций', 'Произведено', 'Затраты ₽']
        st.dataframe(emp_stats, use_container_width=True, hide_index=True)
    else:
        st.info("📭 Нет данных о производстве")
    
    st.markdown("---")
    st.subheader("💰 Структура расходов")
    if not expenses_df.empty:
        category_totals = expenses_df.groupby('category')['amount'].sum().reset_index()
        fig = px.pie(category_totals, values='amount', names='category', title='Расходы по категориям', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 Нет данных о расходах")
    
    st.markdown("---")
    st.subheader("📦 Маржа продукции")
    if not products_df.empty:
        margin_df = products_df[products_df['selling_price'] > 0].copy()
        if not margin_df.empty:
            margin_df['Маржа ₽'] = margin_df['selling_price'] - margin_df['avg_cost']
            margin_df['Маржа %'] = (margin_df['Маржа ₽'] / margin_df['selling_price'] * 100).round(2)
            display_margin = margin_df[['name', 'avg_cost', 'selling_price', 'Маржа ₽', 'Маржа %']].rename(columns={
                'name': 'Продукт',
                'avg_cost': 'Себестоимость ₽',
                'selling_price': 'Цена продажи ₽'
            })
            st.dataframe(display_margin, use_container_width=True, hide_index=True)
        else:
            st.info("📭 Нет продуктов с указанной ценой продажи")
    
    st.markdown("---")
    st.subheader("💼 Финансовая сводка")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total_expenses = expenses_df['amount'].sum() if not expenses_df.empty else 0
        st.metric("💸 Общие расходы", f"{total_expenses:,.2f} ₽")
    with col2:
        stock_value = (products_df['current_stock'] * products_df['avg_cost']).sum() if not products_df.empty else 0
        st.metric("📦 Стоимость запасов", f"{stock_value:,.2f} ₽")
    with col3:
        production_costs = production_df['output_cost'].sum() if not production_df.empty else 0
        st.metric("🏭 Производственные затраты", f"{production_costs:,.2f} ₽")

# ===== СТРАНИЦА: НАСТРОЙКИ =====
elif page == "⚙️ Настройки":
    st.header("⚙️ Настройки системы")
    
    tab1, tab2, tab3 = st.tabs(["📦 Продукты", "👥 Сотрудники", "📁 Категории"])
    
    with tab1:
        st.subheader("📦 Управление продуктами")
        products_df = db.get_products(company_id)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("**Список продуктов:**")
            if not products_df.empty:
                for _, product in products_df.iterrows():
                    st.write(f"**{product['name']}** — {product['category_name']} ({product['unit_name']})")
                    st.caption(f"Остаток: {product['current_stock']} {product['unit_short']}, Себест.: {product['avg_cost']:.2f} ₽")
                    st.markdown("---")
            else:
                st.info("📭 Нет продуктов")
        
        with col2:
            st.markdown("**Добавить продукт:**")
            with st.form("add_product_form"):
                name = st.text_input("Название*")
                categories = db.get_categories()
                category_id = st.selectbox("Категория*", categories['id'], 
                                          format_func=lambda x: categories[categories['id']==x]['name'].values[0])
                units = db.get_units()
                unit_id = st.selectbox("Единица измерения*", units['id'],
                                      format_func=lambda x: f"{units[units['id']==x]['name'].values[0]} ({units[units['id']==x]['short_name'].values[0]})")
                description = st.text_area("Описание")
                min_stock = st.number_input("Минимальный остаток", min_value=0.0, value=0.0, step=1.0)
                selling_price = st.number_input("Цена продажи ₽", min_value=0.0, value=0.0, step=10.0)
                
                if st.form_submit_button("➕ Добавить"):
                    if not name:
                        st.error("⚠️ Укажите название!")
                    else:
                        product_data = {
                            'name': name,
                            'category_id': category_id,
                            'unit_id': unit_id,
                            'description': description,
                            'min_stock': min_stock,
                            'selling_price': selling_price,
                            'current_stock': 0,
                            'avg_cost': 0
                        }
                        db.add_product(company_id, product_data)
                        st.success("✅ Продукт добавлен!")
                        time.sleep(1)
                        st.rerun()
    
    with tab2:
        st.subheader("👥 Управление сотрудниками")
        employees_df = db.get_employees(company_id)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("**Список сотрудников:**")
            if not employees_df.empty:
                for _, emp in employees_df.iterrows():
                    st.write(f"**{emp['name']}** — {emp['position']}")
                    st.caption(f"Ставка: {emp['hourly_rate']:.2f} ₽/час")
                    st.markdown("---")
            else:
                st.info("📭 Нет сотрудников")
        
        with col2:
            st.markdown("**Добавить сотрудника:**")
            with st.form("add_employee_form"):
                name = st.text_input("ФИО*")
                position = st.text_input("Должность")
                hourly_rate = st.number_input("Ставка ₽/час", min_value=0.0, value=0.0, step=50.0)
                
                if st.form_submit_button("➕ Добавить"):
                    if not name:
                        st.error("⚠️ Укажите ФИО!")
                    else:
                        employee_data = {
                            'name': name,
                            'position': position,
                            'hourly_rate': hourly_rate
                        }
                        db.add_employee(company_id, employee_data)
                        st.success("✅ Сотрудник добавлен!")
                        time.sleep(1)
                        st.rerun()
    
    with tab3:
        st.subheader("📁 Справочник категорий")
        categories = db.get_categories()
        
        st.markdown("**Текущие категории:**")
        for _, cat in categories.iterrows():
            st.write(f"**{cat['name']}** — {cat['description']}")
        
        st.info("ℹ️ Категории заполняются автоматически при инициализации базы данных")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'><p>🏭 Универсальный дашборд учета производства и склада | v2.0 с авторизацией</p></div>", unsafe_allow_html=True)
