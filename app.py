import streamlit as st
import psycopg2
import urllib.parse
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
io = __import__('io')

# 1. إعداد الاتصال بقاعدة البيانات السحابية (Pooling)
@st.cache_resource
def init_connection():
    password = urllib.parse.quote_plus("4m-sA.XRZZu!8BW")
    db_url = f"postgresql://postgres.cncdkxgkybutccqthvxq:KB9SX9JCU9rnWEHd@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"
    return psycopg2.connect(db_url)

conn = init_connection()
conn.autocommit = True

def get_file_data(uploaded_file):
    if uploaded_file is not None:
        return uploaded_file.getvalue(), uploaded_file.name
    return None, None

# إنشاء مؤشر عام لتنفيذ الأوامر البسيطة
c = conn.cursor()

# 2. إنشاء الجداول السحابية والتأكد من وجود الأعمدة
c.execute("""CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY, 
    name TEXT, cin TEXT, address TEXT, 
    contract_id TEXT, start_date TEXT, rent_price REAL, phone TEXT,
    shop_category TEXT,
    id_card_file BYTEA, id_card_filename TEXT,
    contract_file BYTEA, contract_filename TEXT,
    conditions_file BYTEA, conditions_filename TEXT
)""")

try:
    c.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS shop_category TEXT;")
except:
    pass

c.execute("""CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY, 
    tenant_id INTEGER, tenant_name TEXT,
    months_paid INTEGER, amount REAL, payment_date TEXT, employee TEXT, paid_months_names TEXT, 
    receipt_file BYTEA, receipt_filename TEXT
)""")

st.set_page_config(page_title="برنامج كراء المحلات", layout="wide", page_icon="🏢")
st.title("🏢 نظام تسيير كراء المحلات التجاري")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "➕ إضافة مكتري", "💰 تسجيل أداء (دفع)", "🏦 تقرير البنك", 
    "⚖️ المتقاعسون", "🔍 البحث والتصفية", "🗑️ تصحيح الأخطاء", "⚙️ إدارة المكترين", "💾 النسخ الاحتياطي"
])

def get_due_status(start_date_str, tenant_id):
    # إنشاء مؤشر محلي مستقل داخل الدالة لمنع أي تعارض في الاتصال
    local_cur = conn.cursor()
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    today = datetime.today().date()
    total_months_since_start = (today.year - start_date.year) * 12 + today.month - start_date.month
    if today.day >= start_date.day:
        total_months_since_start += 1 
    
    local_cur.execute("SELECT SUM(months_paid) FROM payments WHERE tenant_id = %s", (tenant_id,))
    result = local_cur.fetchone()[0]
    local_cur.close()
    
    paid_months = result if result else 0
    
    unpaid_months_count = total_months_since_start - paid_months
    if unpaid_months_count < 0: unpaid_months_count = 0
    
    last_paid_date = start_date + relativedelta(months=int(paid_months))
    month_names_ar = ["يناير", "فبراير", "مارس", "أبريل", "ماي", "يونيو", "يوليوز", "غشت", "شتنبر", "أكتوبر", "نونبر", "دجنبر"]
    next_months_names = []
    for i in range(24):
        due_month_date = last_paid_date + relativedelta(months=i)
        m_name = month_names_ar[due_month_date.month - 1]
        next_months_names.append(f"{m_name} {due_month_date.year}")
    
    unpaid_names = next_months_names[:int(unpaid_months_count)]
    return unpaid_months_count, unpaid_names, next_months_names, paid_months

category_options = ["بيع الدواجن", "بيع اللحوم", "المطاعم", "محلات صنف 1", "محلات صنف 2", "أصناف أخرى"]

# الواجهة 1: إدخال المكترين
with tab1:
    st.subheader("إضافة مكتري جديد")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**إضافة مكتري يدوياً مع المرفقات**")
        with st.form("add_tenant_form", clear_on_submit=True):
            name = st.text_input("الاسم الكامل *")
            phone = st.text_input("رقم الهاتف (للتواصل عبر الواتساب)")
            cin = st.text_input("رقم البطاقة الوطنية")
            address = st.text_input("عنوان أو رقم المحل")
            
            shop_category = st.selectbox("صنف المحل *", options=category_options)
            
            contract = st.text_input("رقم عقد الكراء")
            start_date = st.date_input("تاريخ بداية الكراء")
            rent_price = st.number_input("ثمن الكراء الشهري (درهم) *", min_value=0.0, step=100.0)
            
            st.markdown("**(اختياري) رفع المستندات:**")
            id_card_file = st.file_uploader("نسخة البطاقة الوطنية", type=["pdf", "png", "jpg", "jpeg"], key="add_id_file")
            contract_file = st.file_uploader("نسخة عقد الكراء", type=["pdf", "png", "jpg", "jpeg"], key="add_contract_file")
            conditions_file = st.file_uploader("كناش التحملات", type=["pdf", "png", "jpg", "jpeg"], key="add_cond_file")
            
            submitted = st.form_submit_button("حفظ بيانات المكتري")
            if submitted:
                if name and rent_price > 0:
                    id_bytes, id_name = get_file_data(id_card_file)
                    contract_bytes, contract_name = get_file_data(contract_file)
                    cond_bytes, cond_name = get_file_data(conditions_file)
                    
                    c.execute("""INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, phone,
                                 id_card_file, id_card_filename, contract_file, contract_filename, conditions_file, conditions_filename) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                              (name, cin, address, shop_category, contract, str(start_date), rent_price, phone, 
                               id_bytes, id_name, contract_bytes, contract_name, cond_bytes, cond_name))
                    st.success("تم حفظ المكتري ومرفقاته بنجاح!")
                else:
                    st.error("المرجو إدخال اسم المكتري وثمن الكراء.")
                    
    with col2:
        st.markdown("**استيراد المكترين من ملف Excel 📥**")
        uploaded_file = st.file_uploader("اختر ملف Excel (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            df_excel = pd.read_excel(uploaded_file)
            if st.button("تأكيد استيراد البيانات"):
                for index, row in df_excel.iterrows():
                    t_name = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                    if t_name.strip() != "":
                        t_cin = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                        t_address = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ""
                        t_category = str(row.iloc[3]) if len(row) > 3 and pd.notna(row.iloc[3]) else "محلات صنف 1"
                        t_contract = str(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else ""
                        raw_date = row.iloc[5] if len(row) > 5 and pd.notna(row.iloc[5]) else datetime.today().date()
                        t_date = raw_date.strftime("%Y-%m-%d") if isinstance(raw_date, datetime) else str(datetime.today().date())
                        t_rent = float(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else 0.0
                        t_phone = str(row.iloc[7]) if len(row) > 7 and pd.notna(row.iloc[7]) else ""
                        
                        c.execute("""INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, phone) 
                                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                                  (t_name, t_cin, t_address, t_category, t_contract, t_date, t_rent, t_phone))
                st.success(f"تم استيراد {len(df_excel)} مكتري بنجاح!")

# الواجهة 2: تسجيل الأداءات
with tab2:
    st.subheader("تسجيل أداء جديد مع وصل الدفع")
    selected_filter_cat = st.selectbox("فلترة المكترين حسب الصنف لاختيار أسرع:", options=["الكل"] + category_options, key="pay_cat_filter")
    
    if selected_filter_cat == "الكل":
        tenants_df = pd.read_sql_query("SELECT id, name, rent_price, start_date FROM tenants", conn)
    else:
        tenants_df = pd.read_sql_query("SELECT id, name, rent_price, start_date FROM tenants WHERE shop_category = %s", conn, params=(selected_filter_cat,))
    
    if not tenants_df.empty:
        tenant_dict = dict(zip(tenants_df.name, tenants_df.id))
        selected_tenant = st.selectbox("اختر المكتري", options=list(tenant_dict.keys()))
        t_id = tenant_dict[selected_tenant]
        
        current_tenant_rent = tenants_df.loc[tenants_df['name'] == selected_tenant, 'rent_price'].values[0]
        start_date_str = tenants_df.loc[tenants_df['name'] == selected_tenant, 'start_date'].values[0]
        
        unpaid_count, unpaid_names, next_months_names, paid_months = get_due_status(start_date_str, t_id)
        
        if unpaid_count > 0:
            st.error(f"الأشهر المستحقة المتأخرة: {unpaid_count} شهر")
        
        selected_months = st.multiselect("اختر الأشهر المراد أداؤها:", options=next_months_names, default=unpaid_names if unpaid_count > 0 else [])
        months_paid = len(selected_months)
        calculated_amount = float(current_tenant_rent * months_paid) if current_tenant_rent else 0.0
        
        with st.form("payment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            amount = c1.number_input("المبلغ الإجمالي المدفوع (درهم)", value=calculated_amount, min_value=0.0, step=100.0)
            payment_date = c2.date_input("تاريخ الأداء", datetime.today())
            employee_name = st.text_input("اسم الموظف المستخلص")
            
            st.markdown("**(اختياري) رفع وصل الأداء (التوصيل):**")
            receipt_file = st.file_uploader("اختر صورة أو ملف الوصل", type=["pdf", "png", "jpg", "jpeg"], key="payment_receipt_file")
            
            if st.form_submit_button("تأكيد وتسجيل الأداء"):
                if months_paid == 0:
                    st.warning("المرجو اختيار شهر واحد على الأقل ليتم تسجيله.")
                else:
                    paid_months_str = "، ".join(selected_months)
                    receipt_bytes, receipt_name = get_file_data(receipt_file)
                    
                    c.execute("""INSERT INTO payments (tenant_id, tenant_name, months_paid, amount, payment_date, employee, paid_months_names, receipt_file, receipt_filename) 
                                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                              (t_id, selected_tenant, months_paid, amount, str(payment_date), employee_name, paid_months_str, receipt_bytes, receipt_name))
                    st.success(f"تم تسجيل الأداء بنجاح!")
                    st.rerun()
    else:
        st.warning("لا توجد مكترون في هذا الصنف أو لم تقم بإضافة مكتري بعد.")

# الواجهة 3: تقرير البنك
with tab3:
    st.subheader("تقرير التوريد للبنك")
    d1, d2 = st.columns(2)
    start_d = d1.date_input("من تاريخ", value=datetime.today().replace(day=1))
    end_d = d2.date_input("إلى تاريخ", value=datetime.today())
    
    query = """
        SELECT tenant_name AS "اسم المكتري", 
               months_paid AS "عدد الأشهر", 
               paid_months_names AS "الأشهر المؤداة", 
               amount AS "المبلغ", 
               payment_date AS "تاريخ الأداء", 
               employee AS "الموظف" 
        FROM payments 
        WHERE payment_date BETWEEN %s AND %s
    """
    df = pd.read_sql_query(query, conn, params=(str(start_d), str(end_d)))
    
    if not df.empty:
        st.dataframe(df, width='stretch')
        st.success(f"المبلغ الإجمالي الموجه للبنك: {df['المبلغ'].sum()} درهم")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='التقرير')
        st.download_button(label="📥 تحميل التقرير كملف Excel", data=output.getvalue(), file_name=f"تقرير_البنك.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("لا توجد أداءات في هذه الفترة.")

# الواجهة 4: المتقاعسون والرسالة النموذجية الرسمية
with tab4:
    st.subheader("الإنذارات وإرسال الرسائل الرسمية للمتقاعسين")
    defaulter_filter_cat = st.selectbox("فلترة المتقاعسين حسب الصنف:", options=["الكل"] + category_options, key="def_cat_filter")
    
    if defaulter_filter_cat == "الكل":
        tenants_df = pd.read_sql_query("SELECT DISTINCT id, name, cin, address, shop_category, rent_price, phone, start_date FROM tenants", conn)
    else:
        tenants_df = pd.read_sql_query("SELECT DISTINCT id, name, cin, address, shop_category, rent_price, phone, start_date FROM tenants WHERE shop_category = %s", conn, params=(defaulter_filter_cat,))
        
    defaulters = []
    for index, row in tenants_df.iterrows():
        unpaid_count, unpaid_names, _, _ = get_due_status(row['start_date'], row['id'])
        if unpaid_count > 0:
            defaulters.append({
                "الاسم": row['name'], "البطاقة": row['cin'], "الصنف": row.get('shop_category', ''),
                "الهاتف": row.get('phone', ''), "العنوان": row['address'], "ثمن الكراء": row['rent_price'],
                "عدد أشهر التأخير": unpaid_count, "المبلغ المتأخر": unpaid_count * row['rent_price'],
                "الأشهر المتأخرة": "، ".join(unpaid_names)
            })
            
    if defaulters:
        df_defaulters = pd.DataFrame(defaulters).drop_duplicates(subset=["الاسم"])
        st.dataframe(df_defaulters, width='stretch')
        
        st.markdown("### 📄 المعاينة الرسمية لرسالة الإنذار")
        selected_defaulter = st.selectbox("اختر المكتري لإنشاء رسالة الإنذار:", options=df_defaulters["الاسم"])
        if selected_defaulter:
            d_info = df_defaulters[df_defaulters["الاسم"] == selected_defaulter].iloc[0]
            
            official_letter = f"""المملكة المغربية
عمالة إقليم بنسليمان
جماعة شراط
مصلحة الشؤون المالية و الاقتصادية
الموارد المالية

شراط في: {datetime.today().strftime('%Y-%m-%d')}

من رئيس المجلس الجماعي لشراط
إلى السيد(ة): {d_info['الاسم']}
رقم البطاقة الوطنية: {d_info['البطاقة']}
العنوان (المحل): {d_info['العنوان']} ({d_info['الصنف']})

الموضوع: إنذار بأداء واجبات الكراء.

سلام تام بوجود مولانا الإمام،
وبعد، أخبركم أنكم لم تقوموا بأداء الكراء الشهري عن الأشهر التالية:
({d_info['الأشهر المتأخرة']})

لذا انتم مطالبون بتسوية وضعيتكم الجبائية تجاه الجماعة في أقرب وقت، و ذلك داخل أجل 15 يوما من تاريخ تسلمكم هذه الرسالة.
و نذكركم أنه في حالة عدم تسديد هذا الرسم الذي أصبح ملزماً عليكم، فإن الجماعة ستتخذ جميع الإجراءات الإدارية و القانونية اللازمة لذلك، كما هو مبين في كناش التحملات و عقد الكراء.

والسلام
امضاء الرئيس:"""

            st.text_area("نص الرسالة الرسمية:", official_letter, height=280)
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                docx_output = io.BytesIO()
                docx_output.write(official_letter.encode('utf-8'))
                st.download_button(
                    label="📥 تحميل الرسالة كملف جاهز (Word/Text)",
                    data=docx_output.getvalue(),
                    file_name=f"إنذار_{d_info['الاسم']}.doc",
                    mime="application/msword"
                )
            
            with col_btn2:
                if d_info['الهاتف']:
                    phone_str = str(d_info['الهاتف']).replace("+", "").replace(" ", "")
                    wa_link = f"https://wa.me/{phone_str}?text={urllib.parse.quote(official_letter)}"
                    st.markdown(f'<a href="{wa_link}" target="_blank" style="background-color:#25D366; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold; display:inline-block; text-align:center; width:100%;">📲 إرسال الإنذار عبر الواتساب</a>', unsafe_allow_html=True)
                else:
                    st.warning("رقم الهاتف غير متوفر لهذا المكتري لإرساله عبر الواتساب.")
    else:
        st.success("لا يوجد أي متقاعسين حالياً في هذا الصنف.")

# الواجهة 5: البحث وعرض المرفقات والأشهر غير المؤداة
with tab5:
    st.subheader("البحث عن مكتري وعرض المرفقات وحالة الأشهر")
    search_q = st.text_input("أدخل اسم المكتري (يقبل الحروف الكبيرة والصغيرة):")
    if search_q:
        safe_q = f"%{search_q}%"
        df_search = pd.read_sql_query("SELECT * FROM tenants WHERE name ILIKE %s", conn, params=(safe_q,))
        if not df_search.empty:
            t_data = df_search.iloc[0]
            t_id = t_data['id']
            
            st.markdown(f"### 👤 بيانات المكتري: {t_data['name']}")
            st.write(f"**البطاقة الوطنية:** {t_data['cin']} | **صنف المحل:** {t_data.get('shop_category', 'غير متوفر')} | **الهاتف:** {t_data.get('phone', 'غير متوفر')}")
            st.write(f"**العنوان:** {t_data['address']} | **ثمن الكراء:** {t_data['rent_price']} درهم | **تاريخ البداية:** {t_data['start_date']}")
            
            unpaid_count, unpaid_names, _, paid_months = get_due_status(t_data['start_date'], t_id)
            st.info(f"📊 عدد الأشهر المؤداة سابقاً: {paid_months} شهر | ⚠️ الأشهر المتأخرة غير المؤداة ({unpaid_count} شهر): {', '.join(unpaid_names) if unpaid_names else 'لا توجد متأخرات'}")
            
            st.markdown("#### 📂 الملفات المرفقة:")
            cols = st.columns(3)
            
            id_file_data = t_data.get('id_card_file')
            id_file_name = t_data.get('id_card_filename')
            if id_file_data is not None and id_file_name:
                if isinstance(id_file_data, memoryview):
                    id_file_data = bytes(id_file_data)
                cols[0].download_button("📥 تحميل البطاقة", data=id_file_data, file_name=id_file_name, key=f"dl_id_{t_id}")
            else:
                cols[0].write("البطاقة: ❌ غير متوفرة")
            
            contract_file_data = t_data.get('contract_file')
            contract_file_name = t_data.get('contract_filename')
            if contract_file_data is not None and contract_file_name:
                if isinstance(contract_file_data, memoryview):
                    contract_file_data = bytes(contract_file_data)
                cols[1].download_button("📥 تحميل العقد", data=contract_file_data, file_name=contract_file_name, key=f"dl_contract_{t_id}")
            else:
                cols[1].write("عقد الكراء: ❌ غير متوفر")
            
            cond_file_data = t_data.get('conditions_file')
            cond_file_name = t_data.get('conditions_filename')
            if cond_file_data is not None and cond_file_name:
                if isinstance(cond_file_data, memoryview):
                    cond_file_data = bytes(cond_file_data)
                cols[2].download_button("📥 تحميل الكناش", data=cond_file_data, file_name=cond_file_name, key=f"dl_cond_{t_id}")
            else:
                cols[2].write("كناش التحملات: ❌ غير متوفر")
            
            st.markdown("---")
            st.markdown("### 📜 سجل الأداءات (المدفوعة)")
            df_payments = pd.read_sql_query("SELECT * FROM payments WHERE tenant_id = %s", conn, params=(t_id,))
            if not df_payments.empty:
                for index, p_row in df_payments.iterrows():
                    with st.expander(f"أداء بتاريخ: {p_row['payment_date']} | المبلغ: {p_row['amount']} درهم"):
                        st.write(f"**الأشهر المؤداة:** {p_row['paid_months_names']}")
                        st.write(f"**الموظف المستخلص:** {p_row['employee']}")
                        
                        receipt_data = p_row.get('receipt_file')
                        receipt_name = p_row.get('receipt_filename')
                        if receipt_data is not None and receipt_name:
                            if isinstance(receipt_data, memoryview):
                                receipt_data = bytes(receipt_data)
                            st.download_button("📥 تحميل صورة الوصل", data=receipt_data, file_name=receipt_name, key=f"receipt_{p_row['id']}")
                        else:
                            st.write("صورة الوصل: ❌ غير متوفرة")
            else:
                st.info("لم يقم هذا المكتري بأي أداء بعد.")
        else:
            st.warning("لا يوجد مكتري بهذا الاسم")

# الواجهة 6: تصحيح الأخطاء
with tab6:
    st.subheader("إلغاء عملية أداء تم تسجيلها بالخطأ")
    query_recent = """
        SELECT id AS "رقم العملية", 
               tenant_name AS "اسم المكتري", 
               months_paid AS "عدد الأشهر", 
               paid_months_names AS "الأشهر المؤداة", 
               amount AS "المبلغ", 
               payment_date AS "تاريخ الأداء" 
        FROM payments 
        ORDER BY id DESC 
        LIMIT 50
    """
    df_recent = pd.read_sql_query(query_recent, conn)
    if not df_recent.empty:
        st.dataframe(df_recent, width='stretch')
        c1, c2 = st.columns(2)
        payment_id_to_delete = c1.number_input("أدخل 'رقم العملية' المراد حذفها:", min_value=0, step=1, value=0)
        if c1.button("🗑️ حذف العملية نهائياً"):
            if payment_id_to_delete > 0:
                c.execute("DELETE FROM payments WHERE id = %s", (payment_id_to_delete,))
                st.success("تم الحذف بنجاح!")
                st.rerun()

# الواجهة 7: إدارة المكترين
with tab7:
    st.subheader("إدارة المكترين (تعديل البيانات، الثمن، التاريخ، أو الحذف)")
    manage_filter_cat = st.selectbox("فلترة قائمة الإدارة حسب الصنف:", options=["الكل"] + category_options, key="manage_cat_filter")
    
    if manage_filter_cat == "الكل":
        tenants_edit_df = pd.read_sql_query("SELECT id, name FROM tenants", conn)
    else:
        tenants_edit_df = pd.read_sql_query("SELECT id, name FROM tenants WHERE shop_category = %s", conn, params=(manage_filter_cat,))
        
    if not tenants_edit_df.empty:
        edit_dict = dict(zip(tenants_edit_df.name, tenants_edit_df.id))
        selected_edit_tenant = st.selectbox("اختر المكتري للتعديل:", options=list(edit_dict.keys()))
        t_edit_id = edit_dict[selected_edit_tenant]
        
        st.markdown("---")
        colA, colB = st.columns(2)
        
        with colA:
            st.markdown("#### 📝 تعديل بيانات، ثمن الكراء، وتاريخ البداية")
            c.execute("SELECT phone, shop_category, rent_price, start_date FROM tenants WHERE id = %s", (t_edit_id,))
            res_tenant = c.fetchone()
            current_phone = res_tenant[0] if res_tenant else ""
            current_category = res_tenant[1] if res_tenant and res_tenant[1] else "محلات صنف 1"
            current_rent = float(res_tenant[2]) if res_tenant and res_tenant[2] is not None else 0.0
            current_start_date_str = res_tenant[3] if res_tenant and res_tenant[3] else datetime.today().strftime("%Y-%m-%d")
            
            try:
                parsed_start_date = datetime.strptime(current_start_date_str, "%Y-%m-%d").date()
            except:
                parsed_start_date = datetime.today().date()
            
            cat_index = category_options.index(current_category) if current_category in category_options else 3
            
            with st.form("edit_tenant_form"):
                new_phone = st.text_input("تحديث رقم الهاتف:", value=current_phone if current_phone else "")
                new_category = st.selectbox("تحديث صنف المحل:", options=category_options, index=cat_index)
                new_rent = st.number_input("تحديث ثمن الكراء الشهري (درهم):", value=current_rent, min_value=0.0, step=100.0)
                new_start_date = st.date_input("تحديث تاريخ بداية الكراء:", value=parsed_start_date)
                
                st.markdown("**إضافة أو تحديث المرفقات:**")
                new_id_card = st.file_uploader("رفع/تحديث نسخة البطاقة", type=["pdf", "png", "jpg", "jpeg"], key="edit_id")
                new_contract = st.file_uploader("رفع/تحديث نسخة العقد", type=["pdf", "png", "jpg", "jpeg"], key="edit_contract")
                new_cond = st.file_uploader("رفع/تحديث كناش التحملات", type=["pdf", "png", "jpg", "jpeg"], key="edit_cond")
                
                if st.form_submit_button("حفظ التعديلات"):
                    c.execute("""UPDATE tenants SET phone = %s, shop_category
