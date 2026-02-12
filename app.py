import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import ProductionDB
from datetime import datetime, timedelta
import time
import os

st.set_page_config(page_title="Производственный дашборд", page_icon="🏭", layout="wide")

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

# ========== СТРАНИЦА: ОБЗОР ==========
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
        st.metric("Позиций на складе", len(products_df))
    
    with col2:
        if not products_df.empty:
            total_value = (products_df['current_stock'] * products_df['avg_cost']).sum()
            st.metric("Стоимость запасов", f"{total_value:,.2f} ₽")
        else:
            st.metric("Стоимость запасов", "0 ₽")
    
    with col3:
        total_expenses = expenses_month['amount'].sum() if not expenses_month.empty else 0
        st.metric("Расходы за месяц", f"{total_expenses:,.2f} ₽")
    
    with col4:
        production_count = len(production_month)
        st.metric("Производств за месяц", production_count)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 Текущие запасы")
        if not products_df.empty:
            stock_data = products_df[['name', 'current_stock', 'unit_name', 'category_name']].copy()
            stock_data = stock_data[stock_data['current_stock'] > 0]
            if not stock_data.empty:
                st.dataframe(stock_data, hide_index=True, use_container_width=True)
            else:
                st.info("Склад пуст")
        else:
            st.info("Товары не добавлены")
    
    with col2:
        st.subheader("⚠️ Низкие остатки")
        if not products_df.empty:
            low_stock = products_df[products_df['current_stock'] <= products_df['min_stock']]
            if not low_stock.empty:
                st.dataframe(low_stock[['name', 'current_stock', 'min_stock', 'unit_name']], 
                           hide_index=True, use_container_width=True)
            else:
                st.success("✅ Все товары в норме")
        else:
            st.info("Товары не добавлены")
    
    st.markdown("---")
    st.subheader("📋 Последние движения (неделя)")
    
    if not movements_week.empty:
        movements_display = movements_week[['movement_date', 'product_name', 'movement_type', 
                                           'quantity', 'unit_name', 'employee_name']].head(10)
        movements_display['movement_type'] = movements_display['movement_type'].map({'in': '➕ Приход', 'out': '➖ Расход'})
        st.dataframe(movements_display, hide_index=True, use_container_width=True)
    else:
        st.info("Движений за последнюю неделю нет")

# ========== СТРАНИЦА: СКЛАД ==========
elif page == "📦 Склад":
    st.header("📦 Управление складом")
    
    tab1, tab2, tab3 = st.tabs(["📋 Остатки", "➕ Приход", "➖ Расход"])
    
    with tab1:
        st.subheader("📋 Текущие остатки на складе")
        products_df = db.get_products(company_id)
        
        if not products_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                categories = ['Все'] + products_df['category_name'].unique().tolist()
                selected_category = st.selectbox("Фильтр по категории:", categories)
            with col2:
                show_zero = st.checkbox("Показать товары с нулевым остатком", value=True)
            
            filtered_df = products_df.copy()
            if selected_category != 'Все':
                filtered_df = filtered_df[filtered_df['category_name'] == selected_category]
            if not show_zero:
                filtered_df = filtered_df[filtered_df['current_stock'] > 0]
            
            filtered_df['stock_value'] = filtered_df['current_stock'] * filtered_df['avg_cost']
            st.dataframe(filtered_df[['name', 'category_name', 'current_stock', 'unit_name', 
                       'avg_cost', 'stock_value', 'min_stock']], hide_index=True, use_container_width=True)
            
            total_value = filtered_df['stock_value'].sum()
            st.markdown(f"**Общая стоимость запасов:** {total_value:,.2f} ₽")
        else:
            st.info("Товары не добавлены. Перейдите в раздел 'Настройки'.")
    
    with tab2:
        st.subheader("➕ Оприходование товара")
        products_df = db.get_products(company_id)
        employees_df = db.get_employees(company_id)
        
        if products_df.empty:
            st.warning("⚠️ Сначала добавьте продукты в разделе 'Настройки'")
        else:
            with st.form("income_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    product_id = st.selectbox("Выберите продукт*", options=products_df['id'].tolist(),
                        format_func=lambda x: f"{products_df[products_df['id']==x]['name'].values[0]} ({products_df[products_df['id']==x]['unit_name'].values[0]})")
                    quantity = st.number_input("Количество*", min_value=0.0, value=1.0, step=0.1)
                    price_per_unit = st.number_input("Цена за единицу (₽)*", min_value=0.0, value=0.0, step=0.01)
                
                with col2:
                    movement_date = st.date_input("Дата прихода", value=datetime.now())
                    if not employees_df.empty:
                        employee_id = st.selectbox("Ответственный сотрудник",
                            options=[None] + employees_df['id'].tolist(),
                            format_func=lambda x: "Не указан" if x is None else employees_df[employees_df['id']==x]['name'].values[0])
                    else:
                        employee_id = None
                        st.info("Сотрудники не добавлены")
                    notes = st.text_area("Примечание", placeholder="Например: Закупка у поставщика")
                
                total_cost = quantity * price_per_unit
                st.markdown(f"**Итоговая стоимость:** {total_cost:.2f} ₽")
                
                submitted = st.form_submit_button("💾 Оприходовать", use_container_width=True)
                
                if submitted:
                    if price_per_unit <= 0:
                        st.error("Укажите цену за единицу")
                    elif quantity <= 0:
                        st.error("Укажите количество")
                    else:
                        movement_data = {
                            'product_id': product_id, 'movement_type': 'in', 'quantity': quantity,
                            'price_per_unit': price_per_unit, 'total_cost': total_cost,
                            'employee_id': employee_id, 'notes': notes,
                            'movement_date': movement_date.strftime('%Y-%m-%d')
                        }
                        db.add_stock_movement(company_id, movement_data)
                        st.success(f"✅ Товар успешно оприходован!")
                        st.rerun()
    
    with tab3:
        st.subheader("➖ Списание товара")
        products_df = db.get_products(company_id)
        employees_df = db.get_employees(company_id)
        products_with_stock = products_df[products_df['current_stock'] > 0]
        
        if products_with_stock.empty:
            st.warning("⚠️ Нет товаров для списания")
        else:
            product_id = st.selectbox("Выберите продукт для списания*",
                options=products_with_stock['id'].tolist(),
                format_func=lambda x: f"{products_with_stock[products_with_stock['id']==x]['name'].values[0]} (остаток: {products_with_stock[products_with_stock['id']==x]['current_stock'].values[0]:.2f} {products_with_stock[products_with_stock['id']==x]['unit_name'].values[0]})",
                key="outcome_product_select")
            
            selected_product = products_with_stock[products_with_stock['id']==product_id].iloc[0]
            max_quantity = selected_product['current_stock']
            st.info(f"📦 Доступно на складе: **{max_quantity:.2f} {selected_product['unit_name']}**")
            
            with st.form("outcome_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    quantity = st.number_input(f"Количество для списания*", min_value=0.0,
                        value=min(1.0, float(max_quantity)), step=0.1, help=f"Максимум: {max_quantity:.2f}")
                    movement_date = st.date_input("Дата списания", value=datetime.now(), key="outcome_date")
                
                with col2:
                    if not employees_df.empty:
                        employee_id = st.selectbox("Ответственный сотрудник",
                            options=[None] + employees_df['id'].tolist(),
                            format_func=lambda x: "Не указан" if x is None else employees_df[employees_df['id']==x]['name'].values[0],
                            key="outcome_employee")
                    else:
                        employee_id = None
                    notes = st.text_area("Примечание", placeholder="Например: Продажа, списание брака", key="outcome_notes")
                
                submitted = st.form_submit_button("➖ Списать", use_container_width=True)
                
                if submitted:
                    if quantity <= 0:
                        st.error("Укажите количество больше 0")
                    elif quantity > max_quantity:
                        st.error(f"❌ Недостаточно товара! Доступно: {max_quantity:.2f}")
                    else:
                        movement_data = {
                            'product_id': product_id, 'movement_type': 'out', 'quantity': quantity,
                            'employee_id': employee_id, 'notes': notes,
                            'movement_date': movement_date.strftime('%Y-%m-%d')
                        }
                        db.add_stock_movement(company_id, movement_data)
                        st.success(f"✅ Товар списан! Осталось: {max_quantity - quantity:.2f}")
                        st.rerun()

# ========== СТРАНИЦА: ПРОИЗВОДСТВО ==========
elif page == "🏭 Производство":
    st.header("🏭 Производственный учет")
    
    tab1, tab2 = st.tabs(["➕ Новая операция", "📋 История производства"])
    
    with tab1:
        st.subheader("➕ Добавить производственную операцию")
        products_df = db.get_products(company_id)
        employees_df = db.get_employees(company_id)
        
        if products_df.empty or employees_df.empty:
            st.warning("⚠️ Сначала добавьте продукты и сотрудников")
        else:
            col1, col2 = st.columns(2)
            with col1:
                operation_name = st.text_input("Название операции*", placeholder="Распиловка бревен")
                production_date = st.date_input("Дата производства", value=datetime.now())
            with col2:
                employee_id = st.selectbox("Сотрудник*", options=employees_df['id'].tolist(),
                    format_func=lambda x: employees_df[employees_df['id']==x]['name'].values[0])
                additional_costs = st.number_input("Дополнительные расходы (₽)", min_value=0.0, value=0.0, step=10.0)
            
            st.markdown("---")
            st.markdown("#### 📦 Использованные материалы")
            
            if 'materials_count' not in st.session_state:
                st.session_state.materials_count = 1
            
            materials_used = []
            materials_valid = True
            
            for i in range(st.session_state.materials_count):
                st.markdown(f"**Материал {i+1}:**")
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    material_id = st.selectbox(f"Продукт", options=products_df['id'].tolist(),
                        format_func=lambda x: f"{products_df[products_df['id']==x]['name'].values[0]} (остаток: {products_df[products_df['id']==x]['current_stock'].values[0]:.2f})",
                        key=f"material_id_{i}")
                
                with col2:
                    selected_material = products_df[products_df['id']==material_id].iloc[0]
                    max_qty = selected_material['current_stock']
                    
                    if max_qty <= 0:
                        st.error(f"Нет в наличии")
                        materials_valid = False
                        material_qty = 0
                    else:
                        material_qty = st.number_input(f"Количество (макс: {max_qty:.2f})",
                            min_value=0.0, max_value=float(max_qty), value=min(1.0, float(max_qty)), step=0.1, key=f"material_qty_{i}")
                
                with col3:
                    st.markdown("&nbsp;")
                    st.markdown(f"*{selected_material['unit_name']}*")
                
                material_cost = material_qty * selected_material['avg_cost']
                st.caption(f"Стоимость материала: {material_cost:.2f} ₽")
                materials_used.append({'product_id': material_id, 'quantity_used': material_qty, 'cost': material_cost})
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("➕ Добавить еще материал"):
                    st.session_state.materials_count += 1
                    st.rerun()
            with col2:
                if st.session_state.materials_count > 1:
                    if st.button("➖ Удалить последний"):
                        st.session_state.materials_count -= 1
                        st.rerun()
            
            st.markdown("---")
            st.markdown("#### 📤 Результат производства")
            
            col1, col2 = st.columns(2)
            with col1:
                output_product_id = st.selectbox("Готовая продукция*", options=products_df['id'].tolist(),
                    format_func=lambda x: f"{products_df[products_df['id']==x]['name'].values[0]} ({products_df[products_df['id']==x]['unit_name'].values[0]})")
            with col2:
                output_quantity = st.number_input("Количество произведено*", min_value=0.0, value=1.0, step=0.1)
            
            notes = st.text_area("Примечание")
            
            total_materials_cost = sum([m['cost'] for m in materials_used])
            total_cost = total_materials_cost + additional_costs
            cost_per_unit = total_cost / output_quantity if output_quantity > 0 else 0
            
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Материалы", f"{total_materials_cost:.2f} ₽")
            with col2:
                st.metric("Доп. расходы", f"{additional_costs:.2f} ₽")
            with col3:
                st.metric("Итого", f"{total_cost:.2f} ₽")
            with col4:
                st.metric("Себестоимость/ед", f"{cost_per_unit:.2f} ₽")
            
            if st.button("🏭 Создать производственную операцию", use_container_width=True, type="primary"):
                if not operation_name:
                    st.error("Укажите название операции")
                elif not materials_valid:
                    st.error("Недостаточно материалов на складе")
                elif output_quantity <= 0:
                    st.error("Укажите количество произведенной продукции")
                else:
                    production_data = {
                        'operation_name': operation_name, 'employee_id': employee_id,
                        'output_product_id': output_product_id, 'output_quantity': output_quantity,
                        'output_cost': additional_costs, 'production_date': production_date.strftime('%Y-%m-%d'),
                        'notes': notes
                    }
                    try:
                        db.add_production_operation(company_id, production_data, materials_used)
                        st.success("🎉 **ПРОИЗВОДСТВЕННАЯ ОПЕРАЦИЯ УСПЕШНО СОЗДАНА!**")
                        st.balloons()
                        output_unit = products_df[products_df['id']==output_product_id]['unit_name'].values[0]
                        st.info(f"**Произведено:** {output_quantity:.2f} {output_unit}, **Себестоимость:** {cost_per_unit:.2f} ₽/ед")
                        st.session_state.materials_count = 1
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {str(e)}")
    
    with tab2:
        st.subheader("📋 История производственных операций")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("С даты", value=datetime.now().date() - timedelta(days=30), key="prod_start")
        with col2:
            end_date = st.date_input("По дату", value=datetime.now().date(), key="prod_end")
        
        production_df = db.get_production_operations(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
        if not production_df.empty:
            production_df['cost_per_unit'] = production_df['output_cost'] / production_df['output_quantity']
            
            for idx, row in production_df.iterrows():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                with col1:
                    st.markdown(f"**{row['production_date']}**")
                    st.caption(f"{row['operation_name']}")
                with col2:
                    st.text(f"👷 {row['employee_name']}")
                with col3:
                    st.text(f"📦 {row['output_product_name']}")
                    st.caption(f"{row['output_quantity']:.2f} {row['output_unit']}")
                with col4:
                    st.text(f"💰 {row['output_cost']:.2f} ₽")
                    st.caption(f"{row['cost_per_unit']:.2f} ₽/ед")
                with col5:
                    if st.button("🗑️", key=f"del_{row['id']}", help="Удалить"):
                        result = db.delete_production_operation(row['id'])
                        if result["success"]:
                            st.success("✅ Операция удалена!")
                            st.info(f"Материалов возвращено: {result['materials_returned']}, списано: {result['output_removed']:.2f}")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(result['message'])
                st.markdown("---")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Всего операций", len(production_df))
            with col2:
                st.metric("Произведено единиц", f"{production_df['output_quantity'].sum():.2f}")
            with col3:
                st.metric("Общие расходы", f"{production_df['output_cost'].sum():.2f} ₽")
        else:
            st.info("Производственных операций за выбранный период нет")

# ========== СТРАНИЦА: РАСХОДЫ ==========
elif page == "💰 Расходы":
    st.header("💰 Учет расходов")
    tab1, tab2 = st.tabs(["➕ Добавить расход", "📋 История расходов"])
    
    with tab1:
        with st.form("expense_form"):
            col1, col2 = st.columns(2)
            with col1:
                expense_category = st.selectbox("Категория расхода*",
                    options=["Зарплаты", "Аренда", "Электроэнергия", "Транспорт", "Связь", "Ремонт", "Налоги", "Маркетинг", "Офис", "Другое"])
                amount = st.number_input("Сумма (₽)*", min_value=0.0, value=0.0, step=10.0)
            with col2:
                expense_date = st.date_input("Дата расхода", value=datetime.now())
                description = st.text_area("Описание")
            
            if st.form_submit_button("💾 Добавить расход", use_container_width=True):
                if amount <= 0:
                    st.error("Укажите сумму расхода")
                else:
                    expense_data = {'category': expense_category, 'description': description,
                                   'amount': amount, 'expense_date': expense_date.strftime('%Y-%m-%d')}
                    db.add_expense(company_id, expense_data)
                    st.success("✅ Расход добавлен!")
                    st.rerun()
    
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("С даты", value=datetime.now().date() - timedelta(days=30), key="expense_start")
        with col2:
            end_date = st.date_input("По дату", value=datetime.now().date(), key="expense_end")
        
        expenses_df = db.get_expenses(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
        if not expenses_df.empty:
            st.dataframe(expenses_df[['expense_date', 'category', 'description', 'amount']],
                        hide_index=True, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                category_expenses = expenses_df.groupby('category')['amount'].sum().reset_index()
                fig = px.bar(category_expenses, x='amount', y='category', orientation='h',
                           labels={'amount': 'Сумма (₽)', 'category': 'Категория'}, color='amount')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.metric("Всего расходов", f"{expenses_df['amount'].sum():,.2f} ₽")
                st.metric("Средний расход", f"{expenses_df['amount'].mean():,.2f} ₽")
                st.metric("Максимальный расход", f"{expenses_df['amount'].max():,.2f} ₽")
        else:
            st.info("Расходов за выбранный период нет")

# ========== СТРАНИЦА: АНАЛИТИКА ==========
elif page == "📈 Аналитика":
    st.header("📈 Аналитика и отчеты")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Период с", value=datetime.now().date() - timedelta(days=30), key="analytics_start")
    with col2:
        end_date = st.date_input("Период по", value=datetime.now().date(), key="analytics_end")
    
    movements_df = db.get_stock_movements(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    production_df = db.get_production_operations(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    expenses_df = db.get_expenses(company_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    products_df = db.get_products(company_id)
    
    st.subheader("📊 Динамика движения товаров")
    if not movements_df.empty:
        movements_by_date = movements_df.groupby(['movement_date', 'movement_type'])['quantity'].sum().reset_index()
        movements_by_date['Тип'] = movements_by_date['movement_type'].map({'in': '➕ Приход', 'out': '➖ Расход'})
        fig = px.line(movements_by_date, x='movement_date', y='quantity', color='Тип', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных о движении товаров")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏭 Производительность")
        if not production_df.empty:
            employee_productivity = production_df.groupby('employee_name')['output_quantity'].sum().reset_index()
            fig = px.bar(employee_productivity, x='output_quantity', y='employee_name', orientation='h')
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("💰 Структура расходов")
        if not expenses_df.empty:
            expense_by_category = expenses_df.groupby('category')['amount'].sum().reset_index()
            fig = px.pie(expense_by_category, values='amount', names='category')
            st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("💵 Рентабельность продукции")
    if not products_df.empty:
        products_with_margin = products_df[(products_df['avg_cost'] > 0) & (products_df['selling_price'] > 0)].copy()
        if not products_with_margin.empty:
            products_with_margin['margin'] = products_with_margin['selling_price'] - products_with_margin['avg_cost']
            products_with_margin['margin_percent'] = (products_with_margin['margin'] / products_with_margin['selling_price'] * 100).round(2)
            st.dataframe(products_with_margin[['name', 'avg_cost', 'selling_price', 'margin', 'margin_percent']],
                        hide_index=True, use_container_width=True)

# ========== СТРАНИЦА: НАСТРОЙКИ ==========
elif page == "⚙️ Настройки":
    st.header("⚙️ Настройки системы")
    tab1, tab2, tab3 = st.tabs(["📦 Продукты", "👷 Сотрудники", "📋 Категории"])
    
    with tab1:
        col1, col2 = st.columns([3, 2])
        with col1:
            products_df = db.get_products(company_id)
            if not products_df.empty:
                for _, row in products_df.iterrows():
                    col_name, col_info = st.columns([4, 1])
                    with col_name:
                        st.markdown(f"**{row['name']}** — {row['category_name']} ({row['unit_name']})")
                        st.caption(f"Остаток: {row['current_stock']:.2f}, Цена: {row['selling_price']:.2f} ₽")
                    st.markdown("---")
            else:
                st.info("Продукты не добавлены")
        
        with col2:
            with st.form("add_product_form"):
                name = st.text_input("Название*")
                categories_df = db.get_categories()
                category_id = st.selectbox("Категория*", options=categories_df['id'].tolist(),
                    format_func=lambda x: categories_df[categories_df['id']==x]['name'].values[0])
                units_df = db.get_units()
                unit_id = st.selectbox("Единица*", options=units_df['id'].tolist(),
                    format_func=lambda x: f"{units_df[units_df['id']==x]['name'].values[0]} ({units_df[units_df['id']==x]['short_name'].values[0]})")
                description = st.text_area("Описание")
                min_stock = st.number_input("Минимальный остаток", min_value=0.0, value=0.0, step=1.0)
                selling_price = st.number_input("Цена продажи (₽)", min_value=0.0, value=0.0, step=0.01)
                
                if st.form_submit_button("➕ Добавить", use_container_width=True):
                    if not name:
                        st.error("Укажите название")
                    else:
                        product_data = {'name': name, 'category_id': category_id, 'unit_id': unit_id,
                                       'description': description, 'min_stock': min_stock,
                                       'current_stock': 0, 'avg_cost': 0, 'selling_price': selling_price}
                        db.add_product(company_id, product_data)
                        st.success(f"✅ Продукт '{name}' добавлен!")
                        st.rerun()
    
    with tab2:
        col1, col2 = st.columns([3, 2])
        with col1:
            employees_df = db.get_employees(company_id)
            if not employees_df.empty:
                for _, row in employees_df.iterrows():
                    st.markdown(f"**{row['name']}** — {row['position']}")
                    st.caption(f"Ставка: {row['hourly_rate']:.2f} ₽/час")
                    st.markdown("---")
            else:
                st.info("Сотрудники не добавлены")
        
        with col2:
            with st.form("add_employee_form"):
                emp_name = st.text_input("ФИО*")
                position = st.text_input("Должность")
                hourly_rate = st.number_input("Ставка (₽/час)", min_value=0.0, value=0.0, step=0.5)
                
                if st.form_submit_button("➕ Добавить", use_container_width=True):
                    if not emp_name:
                        st.error("Укажите ФИО")
                    else:
                        employee_data = {'name': emp_name, 'position': position, 'hourly_rate': hourly_rate}
                        db.add_employee(company_id, employee_data)
                        st.success(f"✅ Сотрудник '{emp_name}' добавлен!")
                        st.rerun()
    
    with tab3:
        categories_df = db.get_categories()
        st.markdown("**Текущие категории:**")
        for _, cat in categories_df.iterrows():
            st.write(f"**{cat['name']}** — {cat['type']}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'><p>🏭 Дашборд v2.0 | Авторизация | PostgreSQL</p></div>", unsafe_allow_html=True)
