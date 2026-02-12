import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import ProductionDB
from datetime import datetime, timedelta
import time

# Настройка страницы
st.set_page_config(
    page_title="Производственный дашборд",
    page_icon="🏭",
    layout="wide"
)

# Инициализация базы данных без кэширования
def init_db():
    return ProductionDB()

if 'db' not in st.session_state:
    st.session_state.db = init_db()

db = st.session_state.db

# Заголовок
st.title("🏭 Универсальный дашборд учета производства и склада")
st.markdown("---")

# Боковая панель с навигацией
st.sidebar.title("Навигация")
page = st.sidebar.radio("Выберите раздел:", [
    "📊 Обзор",
    "📦 Склад",
    "🏭 Производство",
    "💰 Расходы",
    "📈 Аналитика",
    "⚙️ Настройки"
])

# ========== СТРАНИЦА: ОБЗОР ==========
if page == "📊 Обзор":
    st.header("📊 Общий обзор")
    
    # Получаем данные
    products_df = db.get_products()
    
    # Период для статистики
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    movements_week = db.get_stock_movements(week_ago.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    expenses_month = db.get_expenses(month_ago.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    production_month = db.get_production_operations(month_ago.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    
    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_products = len(products_df)
        st.metric("Позиций на складе", total_products)
    
    with col2:
        if not products_df.empty:
            total_value = (products_df['current_stock'] * products_df['avg_cost']).sum()
            st.metric("Стоимость запасов", f"{total_value:,.2f} ₽")
        else:
            st.metric("Стоимость запасов", "0 ₽")
    
    with col3:
        if not expenses_month.empty:
            monthly_expenses = expenses_month['amount'].sum()
            st.metric("Расходы за месяц", f"{monthly_expenses:,.2f} ₽")
        else:
            st.metric("Расходы за месяц", "0 ₽")
    
    with col4:
        if not production_month.empty:
            production_count = len(production_month)
            st.metric("Производств за месяц", production_count)
        else:
            st.metric("Производств за месяц", 0)
    
    st.markdown("---")
    
    # Две колонки
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 Текущие запасы")
        if not products_df.empty:
            stock_data = products_df[['name', 'current_stock', 'unit_name', 'category_name']].copy()
            stock_data = stock_data[stock_data['current_stock'] > 0]
            if not stock_data.empty:
                st.dataframe(
                    stock_data,
                    column_config={
                        "name": "Продукт",
                        "current_stock": st.column_config.NumberColumn("Остаток", format="%.2f"),
                        "unit_name": "Ед. изм.",
                        "category_name": "Категория"
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("Склад пуст")
        else:
            st.info("Товары не добавлены")
    
    with col2:
        st.subheader("⚠️ Низкие остатки")
        if not products_df.empty:
            low_stock = products_df[products_df['current_stock'] <= products_df['min_stock']]
            if not low_stock.empty:
                st.dataframe(
                    low_stock[['name', 'current_stock', 'min_stock', 'unit_name']],
                    column_config={
                        "name": "Продукт",
                        "current_stock": st.column_config.NumberColumn("Текущий остаток", format="%.2f"),
                        "min_stock": st.column_config.NumberColumn("Минимум", format="%.2f"),
                        "unit_name": "Ед. изм."
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.success("✅ Все товары в норме")
        else:
            st.info("Товары не добавлены")
    
    # Последние движения
    st.markdown("---")
    st.subheader("📋 Последние движения товаров (неделя)")
    
    if not movements_week.empty:
        movements_display = movements_week[['movement_date', 'product_name', 'movement_type', 
                                           'quantity', 'unit_name', 'employee_name']].head(10)
        movements_display['movement_type'] = movements_display['movement_type'].map({'in': '➕ Приход', 'out': '➖ Расход'})
        
        st.dataframe(
            movements_display,
            column_config={
                "movement_date": "Дата",
                "product_name": "Продукт",
                "movement_type": "Тип",
                "quantity": st.column_config.NumberColumn("Количество", format="%.2f"),
                "unit_name": "Ед. изм.",
                "employee_name": "Сотрудник"
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Движений за последнюю неделю нет")

# ========== СТРАНИЦА: СКЛАД ==========
elif page == "📦 Склад":
    st.header("📦 Управление складом")
    
    tab1, tab2, tab3 = st.tabs(["📋 Остатки", "➕ Приход", "➖ Расход"])
    
    # ========== ОСТАТКИ ==========
    with tab1:
        st.subheader("📋 Текущие остатки на складе")
        
        products_df = db.get_products()
        
        if not products_df.empty:
            # Фильтры
            col1, col2 = st.columns(2)
            with col1:
                categories = ['Все'] + products_df['category_name'].unique().tolist()
                selected_category = st.selectbox("Фильтр по категории:", categories)
            
            with col2:
                show_zero = st.checkbox("Показать товары с нулевым остатком", value=True)
            
            # Применяем фильтры
            filtered_df = products_df.copy()
            
            if selected_category != 'Все':
                filtered_df = filtered_df[filtered_df['category_name'] == selected_category]
            
            if not show_zero:
                filtered_df = filtered_df[filtered_df['current_stock'] > 0]
            
            # Расчет стоимости запасов
            filtered_df['stock_value'] = filtered_df['current_stock'] * filtered_df['avg_cost']
            
            st.dataframe(
                filtered_df[['name', 'category_name', 'current_stock', 'unit_name', 
                           'avg_cost', 'stock_value', 'min_stock']],
                column_config={
                    "name": "Продукт",
                    "category_name": "Категория",
                    "current_stock": st.column_config.NumberColumn("Остаток", format="%.2f"),
                    "unit_name": "Ед. изм.",
                    "avg_cost": st.column_config.NumberColumn("Ср. цена", format="%.2f ₽"),
                    "stock_value": st.column_config.NumberColumn("Стоимость", format="%.2f ₽"),
                    "min_stock": st.column_config.NumberColumn("Мин. остаток", format="%.2f")
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Итого
            total_value = filtered_df['stock_value'].sum()
            st.markdown(f"**Общая стоимость запасов:** {total_value:,.2f} ₽")
        else:
            st.info("Товары не добавлены. Перейдите в раздел 'Настройки' для добавления продуктов.")
    
    # ========== ПРИХОД ==========
    with tab2:
        st.subheader("➕ Оприходование товара")
        
        products_df = db.get_products()
        employees_df = db.get_employees()
        
        if products_df.empty:
            st.warning("⚠️ Сначала добавьте продукты в разделе 'Настройки'")
        else:
            with st.form("income_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    product_id = st.selectbox(
                        "Выберите продукт*",
                        options=products_df['id'].tolist(),
                        format_func=lambda x: f"{products_df[products_df['id']==x]['name'].values[0]} ({products_df[products_df['id']==x]['unit_name'].values[0]})"
                    )
                    
                    quantity = st.number_input("Количество*", min_value=0.0, value=1.0, step=0.1)
                    
                    price_per_unit = st.number_input("Цена за единицу (₽)*", min_value=0.0, value=0.0, step=0.01)
                
                with col2:
                    movement_date = st.date_input("Дата прихода", value=datetime.now())
                    
                    if not employees_df.empty:
                        employee_id = st.selectbox(
                            "Ответственный сотрудник",
                            options=[None] + employees_df['id'].tolist(),
                            format_func=lambda x: "Не указан" if x is None else employees_df[employees_df['id']==x]['name'].values[0]
                        )
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
                            'product_id': product_id,
                            'movement_type': 'in',
                            'quantity': quantity,
                            'price_per_unit': price_per_unit,
                            'total_cost': total_cost,
                            'employee_id': employee_id,
                            'notes': notes,
                            'movement_date': movement_date.strftime('%Y-%m-%d')
                        }
                        
                        db.add_stock_movement(movement_data)
                        st.success(f"✅ Товар успешно оприходован!")
                        st.rerun()
    
    # ========== РАСХОД ==========
    with tab3:
        st.subheader("➖ Списание товара")
        
        products_df = db.get_products()
        employees_df = db.get_employees()
        
        # Только товары с остатком
        products_with_stock = products_df[products_df['current_stock'] > 0]
        
        if products_with_stock.empty:
            st.warning("⚠️ Нет товаров для списания (все остатки нулевые)")
        else:
            # Выбор продукта ВНЕ формы чтобы обновлялось динамически
            product_id = st.selectbox(
                "Выберите продукт для списания*",
                options=products_with_stock['id'].tolist(),
                format_func=lambda x: f"{products_with_stock[products_with_stock['id']==x]['name'].values[0]} (остаток: {products_with_stock[products_with_stock['id']==x]['current_stock'].values[0]:.2f} {products_with_stock[products_with_stock['id']==x]['unit_name'].values[0]})",
                key="outcome_product_select"
            )
            
            selected_product = products_with_stock[products_with_stock['id']==product_id].iloc[0]
            max_quantity = selected_product['current_stock']
            
            st.info(f"📦 Доступно на складе: **{max_quantity:.2f} {selected_product['unit_name']}**")
            
            with st.form("outcome_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    quantity = st.number_input(
                        f"Количество для списания*", 
                        min_value=0.0,
                        value=min(1.0, float(max_quantity)), 
                        step=0.1,
                        help=f"Максимум: {max_quantity:.2f}"
                    )
                    
                    movement_date = st.date_input("Дата списания", value=datetime.now(), key="outcome_date")
                
                with col2:
                    if not employees_df.empty:
                        employee_id = st.selectbox(
                            "Ответственный сотрудник",
                            options=[None] + employees_df['id'].tolist(),
                            format_func=lambda x: "Не указан" if x is None else employees_df[employees_df['id']==x]['name'].values[0],
                            key="outcome_employee"
                        )
                    else:
                        employee_id = None
                        st.info("Сотрудники не добавлены")
                    
                    notes = st.text_area("Примечание", placeholder="Например: Продажа, списание брака", key="outcome_notes")
                
                submitted = st.form_submit_button("➖ Списать", use_container_width=True)
                
                if submitted:
                    if quantity <= 0:
                        st.error("Укажите количество больше 0")
                    elif quantity > max_quantity:
                        st.error(f"❌ Недостаточно товара на складе! Доступно: {max_quantity:.2f} {selected_product['unit_name']}")
                    else:
                        movement_data = {
                            'product_id': product_id,
                            'movement_type': 'out',
                            'quantity': quantity,
                            'employee_id': employee_id,
                            'notes': notes,
                            'movement_date': movement_date.strftime('%Y-%m-%d')
                        }
                        
                        db.add_stock_movement(movement_data)
                        st.success(f"✅ Товар успешно списан! Осталось на складе: {max_quantity - quantity:.2f} {selected_product['unit_name']}")
                        st.rerun()


# ========== СТРАНИЦА: ПРОИЗВОДСТВО ==========
elif page == "🏭 Производство":
    st.header("🏭 Производственный учет")
    
    tab1, tab2 = st.tabs(["➕ Новая операция", "📋 История производства"])
    
    # ========== НОВАЯ ОПЕРАЦИЯ ==========
    with tab1:
        st.subheader("➕ Добавить производственную операцию")
        
        products_df = db.get_products()
        employees_df = db.get_employees()
        
        if products_df.empty:
            st.warning("⚠️ Сначала добавьте продукты в разделе 'Настройки'")
        elif employees_df.empty:
            st.warning("⚠️ Сначала добавьте сотрудников в разделе 'Настройки'")
        else:
            # Форма производственной операции
            st.markdown("#### 📝 Основная информация")
            
            col1, col2 = st.columns(2)
            
            with col1:
                operation_name = st.text_input("Название операции*", placeholder="Например: Распиловка бревен")
                production_date = st.date_input("Дата производства", value=datetime.now())
            
            with col2:
                employee_id = st.selectbox(
                    "Сотрудник*",
                    options=employees_df['id'].tolist(),
                    format_func=lambda x: employees_df[employees_df['id']==x]['name'].values[0]
                )
                
                additional_costs = st.number_input(
                    "Дополнительные расходы (₽)", 
                    min_value=0.0, 
                    value=0.0, 
                    step=10.0,
                    help="Электричество, амортизация оборудования, зарплата и т.д."
                )
            
            st.markdown("---")
            st.markdown("#### 📦 Использованные материалы")
            
            # Динамическое добавление материалов
            if 'materials_count' not in st.session_state:
                st.session_state.materials_count = 1
            
            materials_used = []
            materials_valid = True
            
            for i in range(st.session_state.materials_count):
                st.markdown(f"**Материал {i+1}:**")
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    material_id = st.selectbox(
                        f"Продукт",
                        options=products_df['id'].tolist(),
                        format_func=lambda x: f"{products_df[products_df['id']==x]['name'].values[0]} (остаток: {products_df[products_df['id']==x]['current_stock'].values[0]:.2f} {products_df[products_df['id']==x]['unit_name'].values[0]})",
                        key=f"material_id_{i}"
                    )
                
                with col2:
                    selected_material = products_df[products_df['id']==material_id].iloc[0]
                    max_qty = selected_material['current_stock']
                    
                    if max_qty <= 0:
                        st.error(f"Нет в наличии")
                        materials_valid = False
                        material_qty = 0
                    else:
                        material_qty = st.number_input(
                            f"Количество (макс: {max_qty:.2f})",
                            min_value=0.0,
                            max_value=float(max_qty),
                            value=min(1.0, float(max_qty)),
                            step=0.1,
                            key=f"material_qty_{i}"
                        )
                
                with col3:
                    st.markdown("&nbsp;")
                    st.markdown(f"*{selected_material['unit_name']}*")
                
                material_cost = material_qty * selected_material['avg_cost']
                st.caption(f"Стоимость материала: {material_cost:.2f} ₽")
                
                materials_used.append({
                    'product_id': material_id,
                    'quantity_used': material_qty,
                    'cost': material_cost
                })
            
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
                output_product_id = st.selectbox(
                    "Готовая продукция*",
                    options=products_df['id'].tolist(),
                    format_func=lambda x: f"{products_df[products_df['id']==x]['name'].values[0]} ({products_df[products_df['id']==x]['unit_name'].values[0]})"
                )
            
            with col2:
                output_quantity = st.number_input("Количество произведено*", min_value=0.0, value=1.0, step=0.1)
            
            notes = st.text_area("Примечание", placeholder="Дополнительная информация об операции")
            
            # Расчет себестоимости
            total_materials_cost = sum([m['cost'] for m in materials_used])
            total_cost = total_materials_cost + additional_costs
            cost_per_unit = total_cost / output_quantity if output_quantity > 0 else 0
            
            st.markdown("---")
            st.markdown("#### 💰 Расчет себестоимости")
            
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
                        'operation_name': operation_name,
                        'employee_id': employee_id,
                        'output_product_id': output_product_id,
                        'output_quantity': output_quantity,
                        'output_cost': additional_costs,
                        'production_date': production_date.strftime('%Y-%m-%d'),
                        'notes': notes
                    }
                    
                    try:
                        db.add_production_operation(production_data, materials_used)
                        
                        # 🎉 ЯРКОЕ УВЕДОМЛЕНИЕ
                        st.success("🎉 **ПРОИЗВОДСТВЕННАЯ ОПЕРАЦИЯ УСПЕШНО СОЗДАНА!**")
                        st.balloons()
                        
                        # Показываем детали операции
                        output_unit = products_df[products_df['id']==output_product_id]['unit_name'].values[0]
                        st.info(f"""
**📋 Детали операции:**
- **Операция:** {operation_name}
- **Произведено:** {output_quantity:.2f} {output_unit}
- **Себестоимость:** {cost_per_unit:.2f} ₽/ед
- **Общие затраты:** {total_cost:.2f} ₽
                        """)
                        
                        st.session_state.materials_count = 1
                        time.sleep(2)  # Задержка 2 секунды чтобы пользователь увидел сообщение
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при создании операции: {str(e)}")
    
       # ========== ИСТОРИЯ ПРОИЗВОДСТВА ==========
    with tab2:
        st.subheader("📋 История производственных операций")
        
        # Фильтр по датам
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("С даты", value=datetime.now().date() - timedelta(days=30), key="prod_start")
        with col2:
            end_date = st.date_input("По дату", value=datetime.now().date(), key="prod_end")
        
        production_df = db.get_production_operations(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not production_df.empty:
            # Расчет себестоимости за единицу
            production_df['cost_per_unit'] = production_df['output_cost'] / production_df['output_quantity']
            
            st.markdown("---")
            st.markdown("#### 📋 Список операций")
            
            # Отображаем каждую операцию с кнопкой удаления
            for idx, row in production_df.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**{row['production_date']}**")
                        st.caption(f"{row['operation_name']}")
                    
                    with col2:
                        st.text(f"👷 {row['employee_name']}")
                        st.caption(f"Сотрудник")
                    
                    with col3:
                        st.text(f"📦 {row['output_product_name']}")
                        st.caption(f"{row['output_quantity']:.2f} {row['output_unit']}")
                    
                    with col4:
                        st.text(f"💰 {row['output_cost']:.2f} ₽")
                        st.caption(f"Себестоимость/ед: {row['cost_per_unit']:.2f} ₽")
                    
                    with col5:
                        if st.button("🗑️", key=f"del_prod_op_{row['id']}", help="Удалить операцию и откатить остатки"):
                            try:
                                # Удаляем операцию с автоматическим откатом остатков
                                result = db.delete_production_operation(row['id'])
                                
                                if result["success"]:
                                    st.success(f"✅ Операция '{row['operation_name']}' удалена!")
                                    
                                    # Показываем детали отката
                                    st.info(f"""
**🔄 Откат выполнен:**
- Материалов возвращено: {result['materials_returned']} позиций
- Готовой продукции списано: {result['output_removed']:.2f} {row['output_unit']}
""")
                                    
                                    # Показываем предупреждение если есть
                                    if result.get("warning"):
                                        st.warning(result["warning"])
                                    
                                    time.sleep(3)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                            except Exception as e:
                                st.error(f"❌ Ошибка при удалении: {str(e)}")
                    
                    st.markdown("---")
            
            # Итоговая статистика
            st.markdown("---")
            st.markdown("#### 📊 Итоговая статистика за период")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Всего операций", len(production_df))
            with col2:
                total_produced = production_df['output_quantity'].sum()
                st.metric("Произведено единиц", f"{total_produced:.2f}")
            with col3:
                total_costs = production_df['output_cost'].sum()
                st.metric("Общие расходы", f"{total_costs:.2f} ₽")
        else:
            st.info("Производственных операций за выбранный период нет")
            

# ========== СТРАНИЦА: РАСХОДЫ ==========
elif page == "💰 Расходы":
    st.header("💰 Учет расходов")
    
    tab1, tab2 = st.tabs(["➕ Добавить расход", "📋 История расходов"])
    
    # ========== ДОБАВИТЬ РАСХОД ==========
    with tab1:
        st.subheader("➕ Добавить новый расход")
        
        with st.form("expense_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                expense_category = st.selectbox(
                    "Категория расхода*",
                    options=[
                        "Зарплаты",
                        "Аренда",
                        "Электроэнергия",
                        "Транспорт",
                        "Связь и интернет",
                        "Ремонт оборудования",
                        "Налоги",
                        "Маркетинг",
                        "Офисные расходы",
                        "Другое"
                    ]
                )
                
                amount = st.number_input("Сумма (₽)*", min_value=0.0, value=0.0, step=10.0)
            
            with col2:
                expense_date = st.date_input("Дата расхода", value=datetime.now())
                
                description = st.text_area("Описание", placeholder="Подробности о расходе")
            
            submitted = st.form_submit_button("💾 Добавить расход", use_container_width=True)
            
            if submitted:
                if amount <= 0:
                    st.error("Укажите сумму расхода")
                else:
                    expense_data = {
                        'category': expense_category,
                        'description': description,
                        'amount': amount,
                        'expense_date': expense_date.strftime('%Y-%m-%d')
                    }
                    
                    db.add_expense(expense_data)
                    st.success("✅ Расход успешно добавлен!")
                    st.rerun()
    
    # ========== ИСТОРИЯ РАСХОДОВ ==========
    with tab2:
        st.subheader("📋 История расходов")
        
        # Фильтр по датам
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("С даты", value=datetime.now().date() - timedelta(days=30), key="expense_start")
        with col2:
            end_date = st.date_input("По дату", value=datetime.now().date(), key="expense_end")
        
        expenses_df = db.get_expenses(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not expenses_df.empty:
            st.dataframe(
                expenses_df[['expense_date', 'category', 'description', 'amount']],
                column_config={
                    "expense_date": "Дата",
                    "category": "Категория",
                    "description": "Описание",
                    "amount": st.column_config.NumberColumn("Сумма", format="%.2f ₽")
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Статистика
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📊 Расходы по категориям")
                category_expenses = expenses_df.groupby('category')['amount'].sum().reset_index()
                category_expenses = category_expenses.sort_values('amount', ascending=False)
                
                fig = px.bar(
                    category_expenses,
                    x='amount',
                    y='category',
                    orientation='h',
                    labels={'amount': 'Сумма (₽)', 'category': 'Категория'},
                    color='amount',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 💰 Общая статистика")
                total_expenses = expenses_df['amount'].sum()
                avg_expense = expenses_df['amount'].mean()
                max_expense = expenses_df['amount'].max()
                
                st.metric("Всего расходов", f"{total_expenses:,.2f} ₽")
                st.metric("Средний расход", f"{avg_expense:,.2f} ₽")
                st.metric("Максимальный расход", f"{max_expense:,.2f} ₽")
        else:
            st.info("Расходов за выбранный период нет")

# ========== СТРАНИЦА: АНАЛИТИКА ==========
elif page == "📈 Аналитика":
    st.header("📈 Аналитика и отчеты")
    
    # Период анализа
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Период с", value=datetime.now().date() - timedelta(days=30), key="analytics_start")
    with col2:
        end_date = st.date_input("Период по", value=datetime.now().date(), key="analytics_end")
    
    # Получаем данные
    movements_df = db.get_stock_movements(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    production_df = db.get_production_operations(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    expenses_df = db.get_expenses(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    products_df = db.get_products()
    
    st.markdown("---")
    
    # График движения товаров по дням
    st.subheader("📊 Динамика движения товаров")
    
    if not movements_df.empty:
        # Группируем по датам и типам
        movements_by_date = movements_df.groupby(['movement_date', 'movement_type'])['quantity'].sum().reset_index()
        
        # Переименовываем типы движений для легенды
        movements_by_date['Тип'] = movements_by_date['movement_type'].map({
            'in': '➕ Приход',
            'out': '➖ Расход'
        })
        
        fig = px.line(
            movements_by_date,
            x='movement_date',
            y='quantity',
            color='Тип',
            labels={'movement_date': 'Дата', 'quantity': 'Количество операций'},
            color_discrete_map={'➕ Приход': '#00CC66', '➖ Расход': '#FF3333'},
            markers=True
        )
        
        fig.update_layout(
            xaxis_title="Дата",
            yaxis_title="Количество операций",
            legend_title="Тип движения",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных о движении товаров за выбранный период")
    
    st.markdown("---")
    
    # Две колонки
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏭 Производительность")
        
        if not production_df.empty:
            # По сотрудникам
            employee_productivity = production_df.groupby('employee_name')['output_quantity'].sum().reset_index()
            employee_productivity = employee_productivity.sort_values('output_quantity', ascending=False)
            
            fig = px.bar(
                employee_productivity,
                x='output_quantity',
                y='employee_name',
                orientation='h',
                labels={'output_quantity': 'Произведено единиц', 'employee_name': 'Сотрудник'},
                color='output_quantity',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных о производстве")
    
    with col2:
        st.subheader("💰 Структура расходов")
        
        if not expenses_df.empty:
            expense_by_category = expenses_df.groupby('category')['amount'].sum().reset_index()
            
            fig = px.pie(
                expense_by_category,
                values='amount',
                names='category',
                title='Распределение расходов по категориям'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных о расходах")
    
    st.markdown("---")
    
    # Анализ рентабельности
    st.subheader("💵 Анализ рентабельности продукции")
    
    if not products_df.empty:
        products_with_margin = products_df[
            (products_df['avg_cost'] > 0) & (products_df['selling_price'] > 0)
        ].copy()
        
        if not products_with_margin.empty:
            products_with_margin['margin'] = products_with_margin['selling_price'] - products_with_margin['avg_cost']
            products_with_margin['margin_percent'] = (products_with_margin['margin'] / products_with_margin['selling_price'] * 100).round(2)
            
            st.dataframe(
                products_with_margin[['name', 'avg_cost', 'selling_price', 'margin', 'margin_percent']],
                column_config={
                    "name": "Продукт",
                    "avg_cost": st.column_config.NumberColumn("Себестоимость", format="%.2f ₽"),
                    "selling_price": st.column_config.NumberColumn("Цена продажи", format="%.2f ₽"),
                    "margin": st.column_config.NumberColumn("Маржа", format="%.2f ₽"),
                    "margin_percent": st.column_config.NumberColumn("Маржа %", format="%.2f%%")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Установите цены продажи для продуктов в разделе 'Настройки'")
    
    st.markdown("---")
    
    # Общая финансовая сводка
    st.subheader("💼 Финансовая сводка")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not expenses_df.empty:
            total_expenses = expenses_df['amount'].sum()
            st.metric("Общие расходы", f"{total_expenses:,.2f} ₽")
        else:
            st.metric("Общие расходы", "0 ₽")
    
    with col2:
        if not products_df.empty:
            inventory_value = (products_df['current_stock'] * products_df['avg_cost']).sum()
            st.metric("Стоимость остатков", f"{inventory_value:,.2f} ₽")
        else:
            st.metric("Стоимость остатков", "0 ₽")
    
    with col3:
        if not production_df.empty:
            production_costs = production_df['output_cost'].sum()
            st.metric("Производственные расходы", f"{production_costs:,.2f} ₽")
        else:
            st.metric("Производственные расходы", "0 ₽")

# ========== СТРАНИЦА: НАСТРОЙКИ ==========
elif page == "⚙️ Настройки":
    st.header("⚙️ Настройки системы")
    
    tab1, tab2, tab3 = st.tabs(["📦 Продукты", "👷 Сотрудники", "📋 Категории"])
    
    # ========== ПРОДУКТЫ ==========
    with tab1:
        st.subheader("📦 Управление продуктами")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("#### Список продуктов")
            products_df = db.get_products()
            
            if not products_df.empty:
                # Фильтр по категории
                categories = ['Все'] + products_df['category_name'].unique().tolist()
                filter_cat = st.selectbox("Фильтр:", categories, key="product_filter")
                
                filtered = products_df if filter_cat == 'Все' else products_df[products_df['category_name'] == filter_cat]
                
                st.markdown("---")
                for idx, row in filtered.iterrows():
                    col_name, col_info, col_btn = st.columns([3, 3, 1])
                    
                    with col_name:
                        st.markdown(f"**{row['name']}**")
                        st.caption(f"{row['category_name']} • {row['unit_name']}")
                    
                    with col_info:
                        st.text(f"Остаток: {row['current_stock']:.2f}")
                        st.caption(f"Цена: {row['selling_price']:.2f} ₽")
                    
                    with col_btn:
                        if st.button("🗑️", key=f"del_prod_{row['id']}", help="Удалить продукт"):
                            conn = db.get_connection()
                            cursor = conn.cursor()
                            # Удаляем связанные записи
                            cursor.execute("DELETE FROM stock_movements WHERE product_id=?", (row['id'],))
                            cursor.execute("DELETE FROM production_materials WHERE product_id=?", (row['id'],))
                            cursor.execute("DELETE FROM products WHERE id=?", (row['id'],))
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Продукт '{row['name']}' удален!")
                            st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("Продукты не добавлены")
        
        with col2:
            st.markdown("#### Добавить продукт")
            
            with st.form("add_product_form"):
                name = st.text_input("Название*", placeholder="Например: Доска 50×150×6000")
                
                categories_df = db.get_categories()
                category_id = st.selectbox(
                    "Категория*",
                    options=categories_df['id'].tolist(),
                    format_func=lambda x: categories_df[categories_df['id']==x]['name'].values[0]
                )
                
                units_df = db.get_units()
                unit_id = st.selectbox(
                    "Единица измерения*",
                    options=units_df['id'].tolist(),
                    format_func=lambda x: f"{units_df[units_df['id']==x]['name'].values[0]} ({units_df[units_df['id']==x]['short_name'].values[0]})"
                )
                
                description = st.text_area("Описание", placeholder="Дополнительная информация")
                
                min_stock = st.number_input("Минимальный остаток", min_value=0.0, value=0.0, step=1.0)
                
                selling_price = st.number_input("Цена продажи (₽)", min_value=0.0, value=0.0, step=0.01)
                
                submitted = st.form_submit_button("➕ Добавить", use_container_width=True)
                
                if submitted:
                    if not name:
                        st.error("Укажите название продукта")
                    else:
                        product_data = {
                            'name': name,
                            'category_id': category_id,
                            'unit_id': unit_id,
                            'description': description,
                            'min_stock': min_stock,
                            'current_stock': 0,
                            'avg_cost': 0,
                            'selling_price': selling_price
                        }
                        
                        db.add_product(product_data)
                        st.success(f"✅ Продукт '{name}' добавлен!")
                        st.rerun()
    
    # ========== СОТРУДНИКИ ==========
    with tab2:
        st.subheader("👷 Управление сотрудниками")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("#### Список сотрудников")
            employees_df = db.get_employees()
            
            if not employees_df.empty:
                st.markdown("---")
                for idx, row in employees_df.iterrows():
                    col_name, col_info, col_btn = st.columns([2, 2, 1])
                    
                    with col_name:
                        st.markdown(f"**{row['name']}**")
                    
                    with col_info:
                        st.text(f"{row['position']}")
                        st.caption(f"Ставка: {row['hourly_rate']:.2f} ₽/час")
                    
                    with col_btn:
                        if st.button("🗑️", key=f"del_emp_{row['id']}", help="Удалить сотрудника"):
                            conn = db.get_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM employees WHERE id=?", (row['id'],))
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Сотрудник '{row['name']}' удален!")
                            st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("Сотрудники не добавлены")
        
        with col2:
            st.markdown("#### Добавить сотрудника")
            
            with st.form("add_employee_form"):
                emp_name = st.text_input("ФИО*", placeholder="Иванов Иван Иванович")
                position = st.text_input("Должность", placeholder="Например: Оператор станка")
                hourly_rate = st.number_input("Ставка (₽/час)", min_value=0.0, value=0.0, step=0.5)
                
                submitted = st.form_submit_button("➕ Добавить", use_container_width=True)
                
                if submitted:
                    if not emp_name:
                        st.error("Укажите ФИО сотрудника")
                    else:
                        employee_data = {
                            'name': emp_name,
                            'position': position,
                            'hourly_rate': hourly_rate
                        }
                        
                        db.add_employee(employee_data)
                        st.success(f"✅ Сотрудник '{emp_name}' добавлен!")
                        st.rerun()
    
    # ========== КАТЕГОРИИ ==========
    with tab3:
        st.subheader("📋 Управление категориями")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("#### Список категорий")
            categories_df = db.get_categories()
            
            if not categories_df.empty:
                categories_df['type_name'] = categories_df['type'].map({
                    'raw': 'Сырье',
                    'semifinished': 'Полуфабрикаты',
                    'finished': 'Готовая продукция',
                    'consumables': 'Расходники'
                })
                
                # Отображаем категории с кнопками удаления
                st.markdown("---")
                for idx, row in categories_df.iterrows():
                    col_name, col_type, col_btn = st.columns([2, 2, 1])
                    
                    with col_name:
                        st.markdown(f"**{row['name']}**")
                    
                    with col_type:
                        st.text(row['type_name'])
                    
                    with col_btn:
                        # Проверяем можно ли удалить
                        products_df = db.get_products()
                        has_products = not products_df[products_df['category_id'] == row['id']].empty
                        
                        if has_products:
                            st.button("🗑️", key=f"del_cat_{row['id']}", disabled=True, help="Нельзя удалить: есть продукты в этой категории")
                        else:
                            if st.button("🗑️", key=f"del_cat_{row['id']}", help="Удалить категорию"):
                                conn = db.get_connection()
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM categories WHERE id=?", (row['id'],))
                                conn.commit()
                                conn.close()
                                st.success(f"✅ Категория '{row['name']}' удалена!")
                                st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("Категории не добавлены")
        
        with col2:
            st.markdown("#### Добавить категорию")
            
            with st.form("add_category_form"):
                cat_name = st.text_input("Название*", placeholder="Например: Пиломатериалы")
                
                cat_type = st.selectbox(
                    "Тип*",
                    options=['raw', 'semifinished', 'finished', 'consumables'],
                    format_func=lambda x: {
                        'raw': 'Сырье',
                        'semifinished': 'Полуфабрикаты',
                        'finished': 'Готовая продукция',
                        'consumables': 'Расходники'
                    }[x]
                )
                
                submitted = st.form_submit_button("➕ Добавить", use_container_width=True)
                
                if submitted:
                    if not cat_name:
                        st.error("Укажите название категории")
                    else:
                        try:
                            db.add_category(cat_name, cat_type)
                            st.success(f"✅ Категория '{cat_name}' добавлена!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка: возможно категория уже существует")
            
            st.markdown("---")
            st.markdown("#### 💡 Подсказка")
            st.info("🔒 Удалить можно только категории без продуктов. Сначала удалите или переместите продукты из категории.")

# Футер
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <p>🏭 Универсальный дашборд учета производства и склада | v1.2</p>
    </div>
    """,
    unsafe_allow_html=True
)
