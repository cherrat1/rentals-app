import streamlit as st
import psycopg2
import urllib.parse
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io
import re

# محاولة استدعاء مكتبة الوورد للإنذارات
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# إعدادات الصفحة الأساسية
st.set_page_config(page_title="برنامج كراء المحلات التجارية", layout="wide", page_icon="🏢")

# ---------------------------------------------------------
# 1. نظام تسجيل الدخول والصلاحيات
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""

if not st.session_state["authenticated"]:
    st.title("🔐 تسجيل الدخول إلى نظام إدارة المحلات")
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        submit_login = st.form_submit_button("دخول")
        
        if submit_login:
            if username == "admin" and password == "admin123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "المشرف العام"
                st.session_state["role"] = "SuperAdmin"
                st.success("مرحباً بك أيها المشرف العام!")
                st.rerun()
            elif username == "finance" and password == "fin123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "مشرف الشؤون المالية"
                st.session_state["role"] = "FinanceAdmin"
                st.success("مرحباً بك! تم تسجيل الدخول بصلاحيات المالية.")
                st.rerun()
            elif username == "admin_local" and password == "loc123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "المشرف الإداري"
                st.session_state["role"] = "LocalAdmin"
                st.success("مرحباً بك! تم تسجيل الدخول بصلاحيات الإدارة.")
                st.rerun()
            elif username == "viewer" and password == "view123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "مستخدم مشاهد"
                st.session_state["role"] = "Viewer"
                st.success("مرحباً بك! وضع المشاهدة فقط.")
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")
    st.stop()

# ---------------------------------------------------------
# 2. إعداد الاتصال التراكمي وتخزين الاستعلامات (RAM Caching)
# ---------------------------------------------------------
@st.cache_resource
def init_connection():
    try:
        password = urllib.parse.quote_plus("4m-sA.XRZZu!8BW")
        db_url = f"postgresql://postgres.cncdkxgkybutccqthvxq:KB9SX9JCU9rnWEHd@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error("⚠️ تعذر الاتصال بقاعدة البيانات السحابية.")
        st.stop()

conn = init_connection()
c = conn.cursor()

# دالة الاستعلام السريعة المعتمدة على الذاكرة العشوائية RAM
@st.cache_data(ttl=600, show_spinner=False)
def run_query(query, params=None):
    cur = conn.cursor()
    cur.execute(query, params)
    if cur.description:
        cols = [desc[0] for desc in cur.description]
        data = cur.fetchall()
        cur.close()
        return pd.DataFrame(data, columns=cols)
    cur.close()
    return pd.DataFrame()

# إعادة تعيين الكاش فور التعديل في البيانات
def clear_app_cache():
    st.cache_data.clear()

def get_file_data(uploaded_file):
    if uploaded_file is not None:
        return uploaded_file.getvalue(), uploaded_file.name
    return None, None

def normalize_category_name(cat_input):
    if not cat_input or str(cat_input).lower() == 'nan' or str(cat_input).strip() == '':
        return "أصناف أخرى"
    
    clean_cat = str(cat_input).strip()
    match_num = re.search(r'\d+', clean_cat)
    if match_num and ("صنف" in clean_cat or "محلات" in clean_cat):
        num = int(match_num.group())
        return f"محلات صنف {num}"
        
    return clean_cat

# إنشاء الجداول والفهارس المسرعة (SQL Indexes)
c.execute("""CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY, 
    name TEXT, cin TEXT, address TEXT, 
    contract_id TEXT, start_date TEXT, rent_price REAL, phone TEXT,
    shop_category TEXT,
    id_card_file BYTEA, id_card_filename TEXT,
    contract_file BYTEA, contract_filename TEXT,
    conditions_file BYTEA, conditions_filename TEXT,
    notice_1_file BYTEA, notice_1_filename TEXT,
    notice_2_file BYTEA, notice_2_filename TEXT,
    cancellation_file BYTEA, cancellation_filename TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY, 
    tenant_id INTEGER, tenant_name TEXT,
    months_paid INTEGER, amount REAL, payment_date TEXT, employee TEXT, paid_months_names TEXT, 
    receipt_file BYTEA, receipt_filename TEXT,
    is_sent_to_bank BOOLEAN DEFAULT FALSE
)""")

# إنشاء الفهارس السريعة المباشرة
try:
    c.execute("CREATE INDEX IF NOT EXISTS idx_tenants_cat ON tenants(shop_category);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_tenant ON payments(tenant_id);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);")
except:
    pass

for col_def in ["notice_1_file BYTEA", "notice_1_filename TEXT", "notice_2_file BYTEA", "notice_2_filename TEXT", "cancellation_file BYTEA", "cancellation_filename TEXT", "shop_category TEXT"]:
    try: c.execute(f"ALTER TABLE tenants ADD COLUMN IF NOT EXISTS {col_def};")
    except: pass

try: c.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS is_sent_to_bank BOOLEAN DEFAULT FALSE;")
except: pass

# دالة حساب الوضعية فائقة السرعة
def calculate_due_status_fast(start_date_str, tenant_payments):
    try:
        start_date = datetime.strptime(str(start_date_str), "%Y-%m-%d").date()
    except:
        start_date = datetime.today().date()
        
    today = datetime.today().date()
    paid_month_strings = []
    total_months_paid = 0
    
    for p_names, p_months in tenant_payments:
        if p_names:
            names = [m.strip() for m in str(p_names).replace('،', ',').split(',')]
            paid_month_strings.extend(names)
        if p_months:
            total_months_paid += int(p_months)
            
    month_names_ar = ["يناير", "فبراير", "مارس", "أبريل", "ماي", "يونيو", "يوليوز", "غشت", "شتنبر", "أكتوبر", "نونبر", "دجنبر"]
    
    total_months_since_start = (today.year - start_date.year) * 12 + today.month - start_date.month
    if today.day >= start_date.day:
        total_months_since_start += 1 
        
    if total_months_since_start < 1: total_months_since_start = 1
        
    all_possible_months = []
    unpaid_names = []
    
    for i in range(max(total_months_since_start + 12, 36)):
        due_month_date = start_date + relativedelta(months=i)
        m_name = month_names_ar[due_month_date.month - 1]
        full_m_str = f"{m_name} {due_month_date.year}"
        all_possible_months.append(full_m_str)
        
        if i < total_months_since_start and full_m_str not in paid_month_strings:
            unpaid_names.append(full_m_str)
            
    unpaid_months_count = len(unpaid_names)
    next_available_months = [m for m in all_possible_months if m not in paid_month_strings]
    
    return unpaid_months_count, unpaid_names, next_available_months, total_months_paid

@st.cache_data(ttl=300, show_spinner=False)
def get_all_payments_by_tenant():
    df_p = run_query("SELECT tenant_id, paid_months_names, months_paid FROM payments")
    payments_dict = {}
    if not df_p.empty:
        for _, r in df_p.iterrows():
            tid = int(r['tenant_id']) if pd.notna(r['tenant_id']) else 0
            if tid not in payments_dict: payments_dict[tid] = []
            payments_dict[tid].append((r['paid_months_names'], r['months_paid']))
    return payments_dict

default_categories = ["محلات صنف 1", "محلات صنف 2", "بيع الدواجن", "بيع اللحوم", "المطاعم", "أصناف أخرى"]
try:
    cat_df = run_query("SELECT DISTINCT shop_category FROM tenants WHERE shop_category IS NOT NULL AND shop_category != ''")
    db_categories = cat_df['shop_category'].tolist() if not cat_df.empty else []
    category_options = list(dict.fromkeys([normalize_category_name(c) for c in default_categories + db_categories]))
except:
    category_options = default_categories

# ---------------------------------------------------------
# 3. القائمة الانتقالية السريعة بدلاً من st.tabs المتزامنة
# ---------------------------------------------------------
role = st.session_state["role"]

if role == "SuperAdmin":
    allowed_views = ["➕ إضافة مكتري", "💰 تسجيل أداء", "🏦 تقرير البنك", "⚖️ المتقاعسون", "🔍 البحث والتصفية", "🗑️ تصحيح الأخطاء", "⚙️ إدارة المكترين", "💾 النسخ الاحتياطي"]
elif role == "FinanceAdmin":
    allowed_views = ["💰 تسجيل أداء", "🏦 تقرير البنك", "🔍 البحث والتصفية"]
elif role == "LocalAdmin":
    allowed_views = ["➕ إضافة مكتري", "⚖️ المتقاعسون", "🔍 البحث والتصفية", "⚙️ إدارة المكترين"]
else:
    allowed_views = ["🔍 البحث والتصفية", "🏦 تقرير البنك", "⚖️ المتقاعسون"]

with st.sidebar:
    st.write(f"👤 المستخدم: **{st.session_state['username']}**")
    st.write(f"🛡️ الصلاحية: **{st.session_state['role']}**")
    st.markdown("---")
    active_tab = st.radio("📌 التنقل بين الخدمات:", options=allowed_views, key="active_nav_tab")
    st.markdown("---")
    if st.button("تسجيل الخروج"):
        st.session_state["authenticated"] = False
        st.rerun()

# ---------------------------------------------------------
# الواجهة 1: إضافة مكتري
# ---------------------------------------------------------
if active_tab == "➕ إضافة مكتري":
    st.subheader("إضافة مكتري جديد")
    col1, col2 = st.columns(2)
    with col1:
        with st.form("add_tenant_form", clear_on_submit=True):
            name = st.text_input("الاسم الكامل *")
            phone = st.text_input("رقم الهاتف")
            cin = st.text_input("رقم البطاقة الوطنية")
            address = st.text_input("عنوان أو رقم المحل")
            shop_category = st.selectbox("صنف المحل *", options=category_options)
            contract = st.text_input("رقم عقد الكراء")
            start_date = st.date_input("تاريخ بداية الكراء")
            rent_price = st.number_input("ثمن الكراء الشهري (درهم) *", min_value=0.0, step=100.0)
            
            id_card_file = st.file_uploader("نسخة البطاقة الوطنية", type=["pdf", "png", "jpg", "jpeg"], key="add_id_file")
            contract_file = st.file_uploader("نسخة عقد الكراء", type=["pdf", "png", "jpg", "jpeg"], key="add_contract_file")
            conditions_file = st.file_uploader("كناش التحملات", type=["pdf", "png", "jpg", "jpeg"], key="add_cond_file")
            
            if st.form_submit_button("حفظ بيانات المكتري"):
                if name and rent_price > 0:
                    id_bytes, id_name = get_file_data(id_card_file)
                    contract_bytes, contract_name = get_file_data(contract_file)
                    cond_bytes, cond_name = get_file_data(conditions_file)
                    norm_cat = normalize_category_name(shop_category)
                    
                    c.execute(
                        "INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, phone, "
                        "id_card_file, id_card_filename, contract_file, contract_filename, conditions_file, conditions_filename) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (name, cin, address, norm_cat, contract, str(start_date), rent_price, phone, 
                         id_bytes, id_name, contract_bytes, contract_name, cond_bytes, cond_name)
                    )
                    clear_app_cache()
                    st.success("تم حفظ المكتري بنجاح!")
                    st.rerun()
                else:
                    st.error("المرجو إدخال الاسم وثمن الكراء.")
                    
    with col2:
        st.markdown("**استيراد المكترين من ملف Excel الشامل 📥**")
        template_data = pd.DataFrame([{"اسم المكتري": "أحمد بنجلون", "رقم البطاقة": "AB123456", "تاريخ بداية الكراء": "01/10/2025", "رقم العقد": "C-2024/01", "ثمن الكراء": 1500, "الصنف": "محلات صنف 1", "رقم المحل": "1"}])
        
        template_output = io.BytesIO()
        with pd.ExcelWriter(template_output, engine='xlsxwriter') as template_writer:
            template_data.to_excel(template_writer, index=False, sheet_name='نموذج_الاستيراد')
            wb = template_writer.book
            ws = template_writer.sheets['نموذج_الاستيراد']
            ws.right_to_left()
            header_fmt = wb.add_format({'bold': True, 'bg_color': '#366092', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center'})
            cell_fmt = wb.add_format({'border': 1, 'align': 'center'})
            for c_idx, col_name in enumerate(template_data.columns):
                ws.write(0, c_idx, col_name, header_fmt)
                ws.set_column(c_idx, c_idx, 20)
            for r_idx in range(len(template_data)):
                for c_idx in range(len(template_data.columns)):
                    ws.write(r_idx + 1, c_idx, template_data.iloc[r_idx, c_idx], cell_fmt)

        st.download_button(label="📄 تحميل قالب Excel نموذجي (.xlsx)", data=template_output.getvalue(), file_name="نموذج_استيراد_المكترين.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("---")
        uploaded_file = st.file_uploader("اختر ملف Excel لرفعه (.xlsx)", type=["xlsx"], key="import_full_excel")
        
        if uploaded_file is not None:
            df_excel = pd.read_excel(uploaded_file)
            st.dataframe(df_excel.head(5))
            if st.button("تأكيد استيراد البيانات الشاملة"):
                imported_count = 0
                for index, row in df_excel.iterrows():
                    t_name = str(row.get('اسم المكتري', row.get('الاسم الكامل', ''))).strip()
                    if t_name and t_name != 'nan':
                        t_cin = str(row.get('رقم البطاقة', '')).strip()
                        t_contract = str(row.get('رقم العقد', '')).strip()
                        t_category = normalize_category_name(str(row.get('الصنف', '')))
                        t_shop_num = str(row.get('رقم المحل', '')).strip()
                        raw_date = row.get('تاريخ بداية الكراء', '')
                        try: t_start_date = pd.to_datetime(raw_date, dayfirst=True).strftime('%Y-%m-%d') if pd.notna(raw_date) else str(datetime.today().date())
                        except: t_start_date = str(datetime.today().date())
                        try: t_rent = float(row.get('ثمن الكراء', 0.0))
                        except: t_rent = 0.0
                        
                        c.execute("INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                  (t_name, t_cin, t_shop_num, t_category, t_contract, t_start_date, t_rent))
                        imported_count += 1
                clear_app_cache()
                st.success(f"✅ تم بنجاح استيراد {imported_count} مكتري!")
                st.rerun()

# ---------------------------------------------------------
# الواجهة 2: تسجيل الأداء
# ---------------------------------------------------------
elif active_tab == "💰 تسجيل أداء":
    st.subheader("تسجيل أداء جديد مع وصل الدفع")
    selected_filter_cat = st.selectbox("فلترة المكترين حسب الصنف:", options=["الكل"] + category_options, key="pay_cat_filter")
    
    if selected_filter_cat == "الكل":
        tenants_df = run_query("SELECT id, name, rent_price, start_date FROM tenants")
    else:
        tenants_df = run_query("SELECT id, name, rent_price, start_date FROM tenants WHERE shop_category = %s", (selected_filter_cat,))
    
    if not tenants_df.empty:
        tenant_dict = dict(zip(tenants_df.name, tenants_df.id))
        selected_tenant = st.selectbox("اختر المكتري", options=list(tenant_dict.keys()))
        t_id = int(tenant_dict[selected_tenant])
        current_tenant_rent = float(tenants_df.loc[tenants_df['name'] == selected_tenant, 'rent_price'].values[0])
        start_date_str = str(tenants_df.loc[tenants_df['name'] == selected_tenant, 'start_date'].values[0])
        
        p_df = run_query("SELECT paid_months_names, months_paid FROM payments WHERE tenant_id = %s", (t_id,))
        tenant_payments = list(zip(p_df['paid_months_names'], p_df['months_paid'])) if not p_df.empty else []
        
        unpaid_count, unpaid_names, next_months_names, paid_months = calculate_due_status_fast(start_date_str, tenant_payments)
        selected_months = st.multiselect("اختر الأشهر المراد أداؤها:", options=next_months_names, default=unpaid_names if unpaid_count > 0 else [])
        months_paid = len(selected_months)
        
        with st.form("payment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            payment_date = c1.date_input("تاريخ الأداء", datetime.today())
            employee_name = c2.text_input("اسم الموظف المستخلص")
            is_already_sent = st.checkbox("📌 هذه عملية قديمة تم إرسالها للبنك سابقاً", value=False)
            st.markdown("---")
            receipt_option = st.radio("كيف تريد إرفاق الوصولات؟", options=["📄 وصل واحد يجمع كل الأشهر المحددة", "📑 وصولات منفصلة (رفع عدة ملفات دفعة واحدة)"], horizontal=True)
            
            single_receipt_file = None
            uploaded_multiple_files = []
            
            if months_paid > 0:
                if receipt_option == "📄 وصل واحد يجمع كل الأشهر المحددة":
                    calculated_amount = float(current_tenant_rent * months_paid)
                    st.info(f"**المبلغ الإجمالي:** {calculated_amount} درهم")
                    single_receipt_file = st.file_uploader("إرفاق الوصل الإجمالي", type=["pdf", "png", "jpg", "jpeg"])
                else:
                    st.info(f"اختر {months_paid} ملفات. سيتم ربط كل ملف بشهر تلقائياً.")
                    uploaded_multiple_files = st.file_uploader("إرفاق الوصولات (رفع متعدد)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
            
            if st.form_submit_button("تأكيد وتسجيل الأداء"):
                if months_paid == 0:
                    st.warning("المرجو اختيار شهر واحد على الأقل.")
                else:
                    if receipt_option == "📄 وصل واحد يجمع كل الأشهر المحددة":
                        r_bytes, r_name = get_file_data(single_receipt_file)
                        paid_months_str = "، ".join(selected_months)
                        calculated_amount = float(current_tenant_rent * months_paid)
                        c.execute("INSERT INTO payments (tenant_id, tenant_name, months_paid, amount, payment_date, employee, paid_months_names, receipt_file, receipt_filename, is_sent_to_bank) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                  (t_id, selected_tenant, months_paid, calculated_amount, str(payment_date), employee_name, paid_months_str, r_bytes, r_name, is_already_sent))
                    else:
                        for i, m in enumerate(selected_months):
                            r_file = uploaded_multiple_files[i] if i < len(uploaded_multiple_files) else None
                            r_bytes, r_name = get_file_data(r_file)
                            c.execute("INSERT INTO payments (tenant_id, tenant_name, months_paid, amount, payment_date, employee, paid_months_names, receipt_file, receipt_filename, is_sent_to_bank) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                      (t_id, selected_tenant, 1, current_tenant_rent, str(payment_date), employee_name, m, r_bytes, r_name, is_already_sent))
                    
                    clear_app_cache()
                    st.success("✅ تم تسجيل الأداء بنجاح!")
                    st.rerun()

# ---------------------------------------------------------
# الواجهة 3: تقرير البنك الرسمي
# ---------------------------------------------------------
elif active_tab == "🏦 تقرير البنك":
    st.subheader("🏦 تقرير التوريد للبنك (التتبع والتحيين التلقائي)")
    with st.expander("🛠️ تسوية البيانات القديمة"):
        c_date1, c_date2 = st.columns(2)
        cutoff_date = c_date1.date_input("تحديث كافة العمليات المسجلة حتى تاريخ:", value=datetime.today(), key="cutoff_d")
        if c_date2.button("✅ تحويل كافة العمليات السابقة إلى (مرسلة للبنك)"):
            c.execute("UPDATE payments SET is_sent_to_bank = TRUE WHERE payment_date <= %s AND COALESCE(is_sent_to_bank, FALSE) = FALSE;", (str(cutoff_date),))
            clear_app_cache()
            st.success("✅ تم تحويل جميع العمليات السابقة بنجاح!")
            st.rerun()

    st.markdown("---")
    report_mode = st.radio("اختر نوع التقرير:", ["🆕 العمليات الجديدة (غير المرسلة للبنك)", "📜 أرشيف التقارير السابقة (حسب التاريخ)"], horizontal=True)
    
    if report_mode == "🆕 العمليات الجديدة (غير المرسلة للبنك)":
        query = "SELECT p.tenant_name AS \"اسم المكتري\", COALESCE(NULLIF(MAX(t.contract_id), ''), 'غير متوفر') AS \"رقم العقد\", COALESCE(NULLIF(MAX(t.shop_category), ''), 'غير محدد') AS \"الصنف\", COALESCE(NULLIF(MAX(t.address), ''), 'غير متوفر') AS \"رقم المحل\", SUM(p.months_paid) AS \"عدد الأشهر\", STRING_AGG(p.paid_months_names, '، ') AS \"الأشهر المؤداة\", SUM(p.amount) AS \"المبلغ الإجمالي (درهم)\" FROM payments p LEFT JOIN tenants t ON (p.tenant_id = t.id OR p.tenant_name = t.name) WHERE COALESCE(p.is_sent_to_bank, FALSE) = FALSE GROUP BY p.tenant_name"
        df = run_query(query)
    else:
        d1, d2 = st.columns(2)
        start_d = d1.date_input("من تاريخ", value=datetime.today().replace(day=1), key="b_d1")
        end_d = d2.date_input("إلى تاريخ", value=datetime.today(), key="b_d2")
        query = "SELECT p.tenant_name AS \"اسم المكتري\", COALESCE(NULLIF(MAX(t.contract_id), ''), 'غير متوفر') AS \"رقم العقد\", COALESCE(NULLIF(MAX(t.shop_category), ''), 'غير محدد') AS \"الصنف\", COALESCE(NULLIF(MAX(t.address), ''), 'غير متوفر') AS \"رقم المحل\", SUM(p.months_paid) AS \"عدد الأشهر\", STRING_AGG(p.paid_months_names, '، ') AS \"الأشهر المؤداة\", SUM(p.amount) AS \"المبلغ الإجمالي (درهم)\" FROM payments p LEFT JOIN tenants t ON (p.tenant_id = t.id OR p.tenant_name = t.name) WHERE p.payment_date BETWEEN %s AND %s GROUP BY p.tenant_name"
        df = run_query(query, (str(start_d), str(end_d)))

    if not df.empty:
        total_sum = df["المبلغ الإجمالي (درهم)"].sum()
        df_display_ui = pd.concat([df, pd.DataFrame([{"اسم المكتري": "المجموع", "المبلغ الإجمالي (درهم)": total_sum}])], ignore_index=True)
        st.dataframe(df_display_ui, use_container_width=True)
        st.metric(label="💰 مجموع المبالغ المستخلصة", value=f"{total_sum:,.2f} درهم")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='التقرير')
        st.download_button("📥 تحميل التقرير كملف Excel", data=output.getvalue(), file_name="تقرير_البنك_مجمع_رسمي.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if report_mode == "🆕 العمليات الجديدة (غير المرسلة للبنك)":
            if st.button("🔒 إغلاق هذا التقرير وتأكيد إرساله للبنك"):
                c.execute("UPDATE payments SET is_sent_to_bank = TRUE WHERE COALESCE(is_sent_to_bank, FALSE) = FALSE;")
                clear_app_cache()
                st.success("✅ تم إغلاق التقرير بنجاح!")
                st.rerun()

# ---------------------------------------------------------
# الواجهة 4: المتقاعسون
# ---------------------------------------------------------
elif active_tab == "⚖️ المتقاعسون":
    st.subheader("الإنذارات ومتابعة المراسلات وطلبات الإلغاء")
    defaulter_filter_cat = st.selectbox("فلترة المتقاعسين حسب الصنف:", options=["الكل"] + category_options, key="def_cat_filter")
    q = "SELECT id, name, cin, address, shop_category, rent_price, phone, start_date FROM tenants"
    p = ()
    if defaulter_filter_cat != "الكل":
        q += " WHERE shop_category = %s"
        p = (defaulter_filter_cat,)
        
    tenants_df = run_query(q, p)
    all_payments_dict = get_all_payments_by_tenant()
    
    defaulters = []
    raw_defaulters = []
    for index, row in tenants_df.iterrows():
        t_id = int(row['id'])
        t_payments = all_payments_dict.get(t_id, [])
        unpaid_count, unpaid_names, _, _ = calculate_due_status_fast(str(row['start_date']), t_payments)
        if unpaid_count > 0:
            defaulters.append({"الاسم": row['name'], "الهاتف": row['phone'], "أشهر التأخير": unpaid_count, "المبلغ المتأخر": unpaid_count * row['rent_price'], "الأشهر المعنية": "، ".join(unpaid_names)})
            raw_defaulters.append(row)
            
    if defaulters:
        st.dataframe(pd.DataFrame(defaulters), use_container_width=True)
        if role in ["SuperAdmin", "LocalAdmin"]:
            st.markdown("---")
            selected_def_name = st.selectbox("اختر المكتري لاتخاذ الإجراء:", options=[d['name'] for d in raw_defaulters])
            if selected_def_name:
                s_row = next(item for item in raw_defaulters if item['name'] == selected_def_name)
                sel_id = int(s_row['id'])
                sel_phone = str(s_row['phone'])
                t_payments = all_payments_dict.get(sel_id, [])
                u_cnt, u_nms, _, _ = calculate_due_status_fast(str(s_row['start_date']), t_payments)
                tot_debt = u_cnt * s_row['rent_price']
                
                if sel_phone and sel_phone.lower() != 'nan' and sel_phone.strip() != '':
                    p_clean = sel_phone.replace(" ", "").replace("+", "").replace("-", "")
                    if p_clean.startswith("00212"): p_clean = p_clean[2:]
                    elif p_clean.startswith("0"): p_clean = "212" + p_clean[1:]
                    elif not p_clean.startswith("212"): p_clean = "212" + p_clean
                    msg = f"السلام عليكم السيد(ة) {selected_def_name}، المرجو تسوية وضعية الكراء الخاص بالمحل. الشهور المتأخرة: {u_cnt} أشهر بمبلغ {tot_debt} درهم."
                    st.markdown(f"**تواصل معه مباشرة:** [📱 إرسال رسالة تذكير عبر الواتساب](https://wa.me/{p_clean}?text={urllib.parse.quote(msg)})", unsafe_allow_html=True)
    else:
        st.success("لا توجد متقاعسين.")

# ---------------------------------------------------------
# الواجهة 5: البحث والتصفية
# ---------------------------------------------------------
elif active_tab == "🔍 البحث والتصفية":
    st.subheader("البحث عن مكتري وعرض التفاصيل، الديون، والمرفقات")
    selected_search_cat = st.selectbox("🏷️ فلترة القائمة حسب الصنف لسرعة البحث:", options=["الكل"] + category_options, key="search_cat_filter")
    
    if selected_search_cat == "الكل":
        all_tenants_df = run_query("SELECT id, name, cin, shop_category FROM tenants ORDER BY name ASC")
    else:
        all_tenants_df = run_query("SELECT id, name, cin, shop_category FROM tenants WHERE shop_category = %s ORDER BY name ASC", (selected_search_cat,))
    
    if not all_tenants_df.empty:
        options = [""] + [f"{row['name']} - (بطاقة: {row['cin'] if row['cin'] else 'غير متوفر'}) - [ID: {row['id']}]" for _, row in all_tenants_df.iterrows()]
        selected_option = st.selectbox("🔍 ابدأ بكتابة اسم المكتري:", options=options)
        
        if selected_option:
            t_id = int(selected_option.split("[ID: ")[1].replace("]", ""))
            df_search = run_query("SELECT * FROM tenants WHERE id = %s", (t_id,))
            
            if not df_search.empty:
                row = df_search.iloc[0]
                st.success(f"👤 البيانات الأساسية لـ: {row['name']}")
                col1, col2 = st.columns(2)
                col1.write(f"**الاسم الكامل:** {row['name']} | **رقم البطاقة:** {row.get('cin', 'غير متوفر')}")
                col2.write(f"**تاريخ بداية الكراء:** {row.get('start_date')} | **ثمن الكراء:** {row.get('rent_price')} درهم")
                
                p_df = run_query("SELECT paid_months_names, months_paid FROM payments WHERE tenant_id = %s", (t_id,))
                tenant_payments = list(zip(p_df['paid_months_names'], p_df['months_paid'])) if not p_df.empty else []
                u_cnt, u_nms, _, p_months = calculate_due_status_fast(str(row['start_date']), tenant_payments)
                
                st.info(f"**الأشهر المؤداة:** {p_months} أشهر | **الأشهر المتأخرة:** {u_cnt} أشهر")

# ---------------------------------------------------------
# الواجهة 6: تصحيح وتعديل الأخطاء
# ---------------------------------------------------------
elif active_tab == "🗑️ تصحيح الأخطاء":
    st.subheader("🛠️ تصحيح الأخطاء: تعديل أو إلغاء عمليات الأداء")
    df_recent = run_query("SELECT id AS \"رقم العملية\", tenant_name AS \"اسم المكتري\", amount AS \"المبلغ\", payment_date AS \"تاريخ الأداء\", paid_months_names AS \"الأشهر المستخلصة\" FROM payments ORDER BY id DESC LIMIT 30")
    
    if not df_recent.empty:
        st.dataframe(df_recent, use_container_width=True)
        pay_options = {f"عملية رقم #{row['رقم العملية']} - {row['اسم المكتري']} ({row['الأشهر المستخلصة']})": int(row['رقم العملية']) for _, row in df_recent.iterrows()}
        selected_pay_label = st.selectbox("اختر العملية المراد تعديلها:", options=list(pay_options.keys()))
        
        if selected_pay_label:
            selected_pid = pay_options[selected_pay_label]
            c.execute("SELECT payment_date, employee, paid_months_names FROM payments WHERE id = %s", (selected_pid,))
            p_data = c.fetchone()
            if p_data:
                with st.form("edit_payment_form"):
                    new_pay_date = st.date_input("تحديث تاريخ العملية / الأداء:", value=datetime.strptime(str(p_data[0]), "%Y-%m-%d").date())
                    new_months_names = st.text_input("تحديث الشهر المستخلص:", value=p_data[2] if p_data[2] else "")
                    new_employee = st.text_input("تحديث اسم الموظف المستخلص:", value=p_data[1] if p_data[1] else "")
                    
                    if st.form_submit_button("💾 حفظ تعديلات عملية الأداء"):
                        c.execute("UPDATE payments SET payment_date = %s, paid_months_names = %s, employee = %s WHERE id = %s", (str(new_pay_date), new_months_names, new_employee, selected_pid))
                        clear_app_cache()
                        st.success("✅ تم تحديث بيانات العملية بنجاح!")
                        st.rerun()

# ---------------------------------------------------------
# الواجهة 7: إدارة وتعديل المكترين
# ---------------------------------------------------------
elif active_tab == "⚙️ إدارة المكترين":
    st.subheader("⚙️ إدارة وتعديل المكترين، التواريخ وأرقام العقود")
    selected_edit_cat = st.selectbox("🏷️ فلترة القائمة حسب الصنف لسرعة التعديل والتركيز:", options=["الكل"] + category_options, key="edit_cat_filter")
    
    if selected_edit_cat == "الكل":
        tenants_edit_df = run_query("SELECT id, name, contract_id, cin, address, phone, rent_price, shop_category, start_date FROM tenants ORDER BY id ASC")
    else:
        tenants_edit_df = run_query("SELECT id, name, contract_id, cin, address, phone, rent_price, shop_category, start_date FROM tenants WHERE shop_category = %s ORDER BY id ASC", (selected_edit_cat,))
    
    if not tenants_edit_df.empty:
        edited_df = st.data_editor(tenants_edit_df, disabled=["id"], use_container_width=True, key=f"bulk_tenant_editor_{selected_edit_cat}")
        if st.button("💾 حفظ التعديلات الجماعية من الجدول"):
            for _, row in edited_df.iterrows():
                c.execute("UPDATE tenants SET contract_id = %s, name = %s, cin = %s, address = %s, phone = %s, rent_price = %s, shop_category = %s, start_date = %s WHERE id = %s",
                          (str(row['contract_id']), str(row['name']), str(row['cin']), str(row['address']), str(row['phone']), float(row['rent_price']), normalize_category_name(row['shop_category']), str(row['start_date']), int(row['id'])))
            clear_app_cache()
            st.success("✅ تم حفظ التعديلات بنجاح!")
            st.rerun()

# ---------------------------------------------------------
# الواجهة 8: النسخ الاحتياطي
# ---------------------------------------------------------
elif active_tab == "💾 النسخ الاحتياطي":
    st.subheader("💾 النسخ الاحتياطي والتقرير التفصيلي وحصر المحلات الشاغرة")
    tenants_all_df = run_query("SELECT id, name, cin, address, shop_category, rent_price, start_date FROM tenants ORDER BY shop_category ASC, id ASC")
    all_payments_dict = get_all_payments_by_tenant()

    if not tenants_all_df.empty:
        backup_data = []
        for _, row in tenants_all_df.iterrows():
            t_id = int(row['id'])
            category = normalize_category_name(row['shop_category'])
            t_payments = all_payments_dict.get(t_id, [])
            unpaid_count, _, _, paid_count = calculate_due_status_fast(str(row['start_date']), t_payments)
            rent = float(row['rent_price']) if pd.notna(row['rent_price']) else 0.0
            backup_data.append({"الصنف": category, "اسم المكتري": row['name'], "رقم المحل": row['address'], "ثمن الكراء": rent, "الأشهر المؤداة": paid_count, "الأشهر الغير مؤداة": unpaid_count, "المبالغ الغير مستخلصة": unpaid_count * rent})

        full_backup_df = pd.DataFrame(backup_data)
        st.dataframe(full_backup_df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            full_backup_df.to_excel(writer, index=False, sheet_name="التقرير الشامل")
        st.download_button("📥 تحميل النسخ الاحتياطي", data=output.getvalue(), file_name="النسخ_الاحتياطي_الشامل.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
