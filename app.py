import streamlit as st
import psycopg2
import urllib.parse
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
io = __import__('io')

# 1. إعداد الاتصال بقاعدة البيانات السحابية مع معالجة الأخطاء الذكية
@st.cache_resource
def init_connection():
    try:
        password = urllib.parse.quote_plus("4m-sA.XRZZu!8BW")
        db_url = f"postgresql://postgres.cncdkxgkybutccqthvxq:KB9SX9JCU9rnWEHd@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error("⚠️ تعذر الاتصال بقاعدة البيانات السحابية. يرجى التأكد من تفعيل المشروع في Supabase.")
        st.stop()

conn = init_connection()

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
    local_cur = conn.cursor()
    clean_tenant_id = int(tenant_id)
    clean_start_date_str = str(start_date_str)
    
    start_date = datetime.strptime(clean_start_date_str, "%Y-%m-%d").date()
    today = datetime.today().date()
    total_months_since_start = (today.year - start_date.year) * 12 + today.month - start_date.month
    if today.day >= start_date.day:
        total_months_since_start += 1 
    
    local_cur.execute("SELECT SUM(months_paid) FROM payments WHERE tenant_id = %s", (clean_tenant_id,))
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

# 3. جلب الأصناف المتاحة ديناميكياً لتحديث الفلاتر
default_categories = ["بيع الدواجن", "بيع اللحوم", "المطاعم", "محلات صنف 1", "محلات صنف 2", "أصناف أخرى"]
try:
    c.execute("SELECT DISTINCT shop_category FROM tenants WHERE shop_category IS NOT NULL AND shop_category != ''")
    db_categories = [row[0] for row in c.fetchall()]
    category_options = list(dict.fromkeys(default_categories + db_categories))
except:
    category_options = default_categories

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
        
        excel_default_category = st.selectbox("اختر الصنف الذي ينتمي له هؤلاء المكترون:", options=category_options, key="excel_cat")
        
        uploaded_file = st.file_uploader("اختر ملف Excel (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            df_excel = pd.read_excel(uploaded_file)
            if st.button("تأكيد استيراد البيانات"):
                
                def get_val(row, hints, default_val=""):
                    for col in df_excel.columns:
                        for hint in hints:
                            if hint in str(col):
                                val = row[col]
                                return val if pd.notna(val) else default_val
                    return default_val
                
                imported_count = 0
                for index, row in df_excel.iterrows():
                    t_name = str(get_val(row, ["الاسم", "اسم"]))
                    if t_name.strip() != "" and t_name.strip() != "nan":
                        
                        raw_date = get_val(row, ["تاريخ", "بداية"], datetime.today().date())
                        try:
                            t_date = pd.to_datetime(raw_date).strftime("%Y-%m-%d")
                        except:
                            t_date = str(datetime.today().date())
                            
                        try:
                            t_rent = float(get_val(row, ["ثمن", "كراء"], 0.0))
                        except:
                            t_rent = 0.0
                            
                        t_cin = str(get_val(row, ["بطاقة", "وطنية", "CIN"]))
                        t_address = str(get_val(row, ["عنوان", "محل"]))
                        t_contract = str(get_val(row, ["محضر", "عقد"]))
                        
                        raw_cat_excel = str(get_val(row, ["صنف", "نوع", "فئة", "نشاط"])).strip()
                        if raw_cat_excel != "" and raw_cat_excel != "nan":
                            t_category = raw_cat_excel
                        else:
                            t_category = excel_default_category
                            
                        t_phone = ""
                        
                        if t_cin == "nan": t_cin = ""
                        if t_address == "nan": t_address = ""
                        if t_contract == "nan": t_contract = ""
                        
                        c.execute("""INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, phone) 
                                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                                  (t_name, t_cin, t_address, t_category, t_contract, t_date, t_rent, t_phone))
                        imported_count += 1
                        
                st.success(f"تم بنجاح استيراد {imported_count} مكتري، وتم تصنيفهم في صنف: {excel_default_category}!")

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
        t_id = int(tenant_dict[selected_tenant])
        
        current_tenant_rent = float(tenants_df.loc[tenants_df['name'] == selected_tenant, 'rent_price'].values[0])
        start_date_str = str(tenants_df.loc[tenants_df['name'] == selected_tenant, 'start_date'].values[0])
        
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
                    st.warning("المرجو اختيار شهر واحد
