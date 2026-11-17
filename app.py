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
    except Exception:
        st.error("⚠️ تعذر الاتصال بقاعدة البيانات السحابية.")
        st.stop()

conn = init_connection()
c = conn.cursor()

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

def clear_app_cache():
    st.cache_data.clear()

def get_file_data(uploaded_file):
    if uploaded_file is not None:
        return uploaded_file.getvalue(), uploaded_file.name
    return None, None

# ---------------------------------------------------------
# دوال مستقلة غير مخزنة في الكاش لجلب الملفات الثنائية (BYTEA) عند الطلب
# ---------------------------------------------------------
def get_receipt_bytes(payment_id):
    try:
        cur = conn.cursor()
        cur.execute("SELECT receipt_file, receipt_filename FROM payments WHERE id = %s", (payment_id,))
        res = cur.fetchone()
        cur.close()
        if res and res[0]:
            return bytes(res[0]), res[1]
    except Exception:
        pass
    return None, None

def get_tenant_file(tenant_id, file_col, name_col):
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {file_col}, {name_col} FROM tenants WHERE id = %s", (tenant_id,))
        res = cur.fetchone()
        cur.close()
        if res and res[0]:
            return bytes(res[0]), res[1]
    except Exception:
        pass
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

# إنشاء الجداول وتحديث الأعمدة
c.execute("""CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY, 
    name TEXT, cin TEXT, address TEXT, 
    contract_id TEXT, start_date TEXT, rent_price REAL, phone TEXT,
    shop_category TEXT,
    status TEXT DEFAULT 'نشط',
    end_date TEXT,
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

try:
    c.execute("CREATE INDEX IF NOT EXISTS idx_tenants_cat ON tenants(shop_category);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_tenant ON payments(tenant_id);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);")
except Exception:
    pass

for col_def in [
    "notice_1_file BYTEA", "notice_1_filename TEXT",
    "notice_2_file BYTEA", "notice_2_filename TEXT",
    "cancellation_file BYTEA", "cancellation_filename TEXT",
    "shop_category TEXT", "status TEXT DEFAULT 'نشط'", "end_date TEXT"
]:
    try:
        c.execute(f"ALTER TABLE tenants ADD COLUMN IF NOT EXISTS {col_def};")
    except Exception:
        pass

try:
    c.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS is_sent_to_bank BOOLEAN DEFAULT FALSE;")
except Exception:
    pass

# ترحيل تلقائي للمكترين الذين سبق رفع طلب إلغاء/إفراغ لهم ولم تُحدد حالتهم بعد
try:
    c.execute("""
        UPDATE tenants 
        SET status = 'ملغى / موقوف', 
            end_date = COALESCE(NULLIF(end_date, ''), TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD'))
        WHERE cancellation_filename IS NOT NULL 
          AND cancellation_filename != '' 
          AND (status IS NULL OR status = '');
    """)
    c.execute("UPDATE tenants SET status = 'نشط' WHERE status IS NULL OR status = '';")
except Exception:
    pass

# دالة حساب الوضعية فائقة السرعة مع مراعاة إيقاف الكراء عند الإلغاء
def calculate_due_status_fast(start_date_str, tenant_payments, status="نشط", end_date_str=None):
    try:
        start_date = datetime.strptime(str(start_date_str), "%Y-%m-%d").date()
    except Exception:
        start_date = datetime.today().date()
        
    today = datetime.today().date()
    is_cancelled = (str(status).strip() == "ملغى / موقوف")
    
    if is_cancelled and end_date_str and str(end_date_str).strip() not in ("", "None", "nan"):
        try:
            cutoff_date = datetime.strptime(str(end_date_str).strip(), "%Y-%m-%d").date()
        except Exception:
            cutoff_date = today
    else:
        cutoff_date = today

    paid_month_strings = []
    total_months_paid = 0
    
    for p_names, p_months in tenant_payments:
        if p_names:
            names = [m.strip() for m in str(p_names).replace('،', ',').split(',')]
            paid_month_strings.extend(names)
        if p_months:
            total_months_paid += int(p_months)
            
    month_names_ar = ["يناير", "فبراير", "مارس", "أبريل", "ماي", "يونيو", "يوليوز", "غشت", "شتنبر", "أكتوبر", "نونبر", "دجنبر"]
    
    if is_cancelled and cutoff_date < start_date:
        total_months_due = 0
    else:
        total_months_due = (cutoff_date.year - start_date.year) * 12 + cutoff_date.month - start_date.month
        if cutoff_date.day >= start_date.day:
            total_months_due += 1
        if total_months_due < 1 and not is_cancelled:
            total_months_due = 1
        elif total_months_due < 0:
            total_months_due = 0
        
    all_possible_months = []
    unpaid_names = []
    
    loop_limit = total_months_due if is_cancelled else max(total_months_due + 12, 36)
    for i in range(loop_limit):
        due_month_date = start_date + relativedelta(months=i)
        m_name = month_names_ar[due_month_date.month - 1]
        full_m_str = f"{m_name} {due_month_date.year}"
        all_possible_months.append(full_m_str)
        
        if i < total_months_due and full_m_str not in paid_month_strings:
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
            if tid not in payments_dict:
                payments_dict[tid] = []
            payments_dict[tid].append((r['paid_months_names'], r['months_paid']))
    return payments_dict

default_categories = ["محلات صنف 1", "محلات صنف 2", "بيع الدواجن", "بيع اللحوم", "المطاعم", "أصناف أخرى"]
try:
    cat_df = run_query("SELECT DISTINCT shop_category FROM tenants WHERE shop_category IS NOT NULL AND shop_category != ''")
    db_categories = cat_df['shop_category'].tolist() if not cat_df.empty else []
    category_options = list(dict.fromkeys([normalize_category_name(c) for c in default_categories + db_categories]))
except Exception:
    category_options = default_categories

# ---------------------------------------------------------
# 3. القائمة الانتقالية السريعة (Lazy Navigation)
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
                        "INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, phone, status, "
                        "id_card_file, id_card_filename, contract_file, contract_filename, conditions_file, conditions_filename) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'نشط', %s, %s, %s, %s, %s, %s)",
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
        template_data = pd.DataFrame([
            {"اسم المكتري": "أحمد بنجلون", "رقم البطاقة": "AB123456", "تاريخ بداية الكراء": "01/10/2025", "رقم العقد": "C-2024/01", "ثمن الكراء": 1500, "الصنف": "محلات صنف 1", "رقم المحل": "1"},
            {"اسم المكتري": "فاطمة الزهراء", "رقم البطاقة": "CD789012", "تاريخ بداية الكراء": "15/02/2024", "رقم العقد": "C-2024/02", "ثمن الكراء": 2000, "الصنف": "محلات صنف 1", "رقم المحل": "2"}
        ])
        
        template_output = io.BytesIO()
        with pd.ExcelWriter(template_output, engine='xlsxwriter') as template_writer:
            template_data.to_excel(template_writer, index=False, sheet_name='نموذج_الاستيراد')
            wb = template_writer.book
            ws = template_writer.sheets['نموذج_الاستيراد']
            ws.right_to_left()
            header_fmt = wb.add_format({'bold': True, 'bg_color': '#366092', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            cell_fmt = wb.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
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
                for _, row in df_excel.iterrows():
                    t_name = str(row.get('اسم المكتري', row.get('الاسم الكامل', ''))).strip()
                    if t_name and t_name != 'nan':
                        t_cin = str(row.get('رقم البطاقة', '')).strip()
                        t_contract = str(row.get('رقم العقد', '')).strip()
                        t_category = normalize_category_name(str(row.get('الصنف', '')))
                        t_shop_num = str(row.get('رقم المحل', '')).strip()
                        raw_date = row.get('تاريخ بداية الكراء', '')
                        try:
                            t_start_date = pd.to_datetime(raw_date, dayfirst=True).strftime('%Y-%m-%d') if pd.notna(raw_date) else str(datetime.today().date())
                        except Exception:
                            t_start_date = str(datetime.today().date())
                        try:
                            t_rent = float(row.get('ثمن الكراء', 0.0))
                        except Exception:
                            t_rent = 0.0
                        
                        c.execute("INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'نشط')",
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
    c_filt1, c_filt2 = st.columns([2, 1])
    selected_filter_cat = c_filt1.selectbox("فلترة المكترين حسب الصنف:", options=["الكل"] + category_options, key="pay_cat_filter")
    include_cancelled_pay = c_filt2.checkbox("إظهار العقود الموقوفة (لتسوية ديون سابقة)", value=False)
    
    base_q = "SELECT id, name, rent_price, start_date, COALESCE(status, 'نشط') AS status, end_date FROM tenants WHERE 1=1"
    q_params = []
    if not include_cancelled_pay:
        base_q += " AND COALESCE(status, 'نشط') = 'نشط'"
    if selected_filter_cat != "الكل":
        base_q += " AND shop_category = %s"
        q_params.append(selected_filter_cat)
        
    tenants_df = run_query(base_q, tuple(q_params) if q_params else None)
    
    if not tenants_df.empty:
        tenant_dict = dict(zip(tenants_df.name, tenants_df.id))
        selected_tenant = st.selectbox("اختر المكتري", options=list(tenant_dict.keys()))
        t_id = int(tenant_dict[selected_tenant])
        t_row = tenants_df.loc[tenants_df['id'] == t_id].iloc[0]
        current_tenant_rent = float(t_row['rent_price'])
        start_date_str = str(t_row['start_date'])
        t_status = str(t_row['status'])
        t_end_date = t_row['end_date']
        
        if t_status == "ملغى / موقوف":
            st.warning(f"⚠️ هذا العقد موقوف/ملغى بتاريخ **{t_end_date}**. تظهر فقط الأشهر المستحقة قبل الإيقاف.")
        
        p_df = run_query("SELECT paid_months_names, months_paid FROM payments WHERE tenant_id = %s", (t_id,))
        tenant_payments = list(zip(p_df['paid_months_names'], p_df['months_paid'])) if not p_df.empty else []
        
        unpaid_count, unpaid_names, next_months_names, paid_months = calculate_due_status_fast(start_date_str, tenant_payments, t_status, t_end_date)
        selected_months = st.multiselect("اختر الأشهر المراد أداؤها:", options=next_months_names, default=unpaid_names if unpaid_count > 0 else [])
        months_paid = len(selected_months)
        
        with st.form("payment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            payment_date = c1.date_input("تاريخ الأداء", datetime.today())
            employee_name = c2.text_input("اسم الموظف المستخلص")
            is_already_sent = st.checkbox("📌 هذه عملية قديمة تم إرسالها للبنك سابقاً (إدخال للأرشيف والبحث فقط)", value=False)
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
    else:
        st.info("لا يوجد مكترون مطابقون لمعايير الفلترة.")

# ---------------------------------------------------------
# الواجهة 3: تقرير البنك الرسمي
# ---------------------------------------------------------
elif active_tab == "🏦 تقرير البنك":
    st.subheader("🏦 تقرير التوريد للبنك (التتبع والتحيين التلقائي)")
    with st.expander("🛠️ تسوية البيانات القديمة (تصفية العمليات المدخلة سابقاً)"):
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
        def clean_shop_num(row):
            shop_val = str(row["رقم المحل"])
            cat_val = str(row["الصنف"])
            if cat_val != "غير محدد" and cat_val in shop_val:
                cleaned = shop_val.replace(cat_val, "").strip(" -_:")
                return cleaned if cleaned else shop_val
            return shop_val

        df["رقم المحل"] = df.apply(clean_shop_num, axis=1)
        total_sum = df["المبلغ الإجمالي (درهم)"].sum()
        
        df_display_ui = pd.concat([df, pd.DataFrame([{"اسم المكتري": "المجموع", "المبلغ الإجمالي (درهم)": total_sum}])], ignore_index=True)
        st.dataframe(df_display_ui, use_container_width=True)
        st.metric(label="💰 مجموع المبالغ المستخلصة لهذا التقرير", value=f"{total_sum:,.2f} درهم")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('التقرير')
            worksheet.right_to_left()
            worksheet.set_landscape()
            worksheet.set_paper(9) # A4
            worksheet.fit_to_pages(1, 0)
            worksheet.hide_gridlines(0)
            
            header_right_fmt = workbook.add_format({'bold': True, 'font_size': 11, 'align': 'right', 'valign': 'vcenter'})
            title_center_fmt = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter', 'font_color': '#1B365D'})
            table_header_fmt = workbook.add_format({'border': 1, 'bold': True, 'bg_color': '#366092', 'font_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter', 'font_size': 12})
            cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 11})
            total_label_fmt = workbook.add_format({'border': 1, 'bold': True, 'bg_color': '#D4EDDA', 'font_color': '#155724', 'align': 'center', 'valign': 'vcenter', 'font_size': 12})
            total_amount_fmt = workbook.add_format({'border': 1, 'bold': True, 'bg_color': '#D4EDDA', 'font_color': '#155724', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'num_format': '#,##0.00'})
            date_bottom_fmt = workbook.add_format({'bold': True, 'font_size': 11, 'align': 'left', 'valign': 'vcenter'})

            worksheet.write(0, 0, "المملكة المغربية", header_right_fmt)
            worksheet.write(1, 0, "وزارة الداخلية", header_right_fmt)
            worksheet.write(2, 0, "عمالة بن سليمان", header_right_fmt)
            worksheet.write(3, 0, "جماعة شراط", header_right_fmt)
            worksheet.write(4, 0, "مصلحة المداخيل", header_right_fmt)
            
            worksheet.merge_range(1, 1, 3, 5, "منتوج كراء المحلات المهنية و التجارية", title_center_fmt)
            for r in range(5):
                worksheet.set_row(r, 20)
            worksheet.set_row(5, 15)
            
            header_row = 6
            worksheet.set_row(header_row, 28)
            for col_num, col_name in enumerate(df.columns):
                worksheet.write(header_row, col_num, col_name, table_header_fmt)
                
            data_start_row = 7
            for row_num in range(len(df)):
                current_r = data_start_row + row_num
                worksheet.set_row(current_r, 24)
                for col_num in range(len(df.columns)):
                    val = df.iloc[row_num, col_num]
                    worksheet.write(current_r, col_num, val, cell_fmt)
                    
            total_row_idx = data_start_row + len(df)
            worksheet.set_row(total_row_idx, 26)
            worksheet.merge_range(total_row_idx, 0, total_row_idx, 5, "المجموع", total_label_fmt)
            worksheet.write(total_row_idx, 6, total_sum, total_amount_fmt)
            
            date_row_idx = total_row_idx + 2
            worksheet.set_row(date_row_idx, 22)
            today_str = datetime.today().strftime("%Y-%m-%d")
            worksheet.merge_range(date_row_idx, 4, date_row_idx, 6, f"حرر بشراط في: {today_str}", date_bottom_fmt)
            
            col_widths = {"اسم المكتري": 26, "رقم العقد": 15, "الصنف": 18, "رقم المحل": 12, "عدد الأشهر": 12, "الأشهر المؤداة": 36, "المبلغ الإجمالي (درهم)": 22}
            for i, col_name in enumerate(df.columns):
                w = col_widths.get(col_name, 18)
                worksheet.set_column(i, i, w)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.download_button("📥 تحميل التقرير كملف Excel", data=output.getvalue(), file_name="تقرير_البنك_مجمع_رسمي.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if report_mode == "🆕 العمليات الجديدة (غير المرسلة للبنك)":
            with col_btn2:
                if st.button("🔒 إغلاق هذا التقرير وتأكيد إرساله للبنك"):
                    c.execute("UPDATE payments SET is_sent_to_bank = TRUE WHERE COALESCE(is_sent_to_bank, FALSE) = FALSE;")
                    clear_app_cache()
                    st.success("✅ تم إغلاق التقرير بنجاح!")
                    st.rerun()
    else:
        st.info("لا توجد أداءات مسجلة في هذه الفترة.")

# ---------------------------------------------------------
# الواجهة 4: المتقاعسون وطلبات الإلغاء (إيقاف الكراء)
# ---------------------------------------------------------
elif active_tab == "⚖️ المتقاعسون":
    st.subheader("الإنذارات، طلبات الإلغاء (إيقاف الكراء)، ومتابعة المتقاعسين")
    
    c_f1, c_f2 = st.columns(2)
    defaulter_filter_cat = c_f1.selectbox("فلترة حسب الصنف:", options=["الكل"] + category_options, key="def_cat_filter")
    status_filter = c_f2.selectbox("حالة العقد:", options=["العقود النشطة فقط", "الكل (نشط + ملغى)", "العقود الملغاة / الموقوفة فقط"], key="def_status_filter")
    
    q = "SELECT id, name, cin, address, shop_category, rent_price, phone, start_date, COALESCE(status, 'نشط') AS status, end_date FROM tenants WHERE 1=1"
    p = []
    if defaulter_filter_cat != "الكل":
        q += " AND shop_category = %s"
        p.append(defaulter_filter_cat)
    if status_filter == "العقود النشطة فقط":
        q += " AND COALESCE(status, 'نشط') = 'نشط'"
    elif status_filter == "العقود الملغاة / الموقوفة فقط":
        q += " AND COALESCE(status, 'نشط') = 'ملغى / موقوف'"
        
    tenants_df = run_query(q, tuple(p) if p else None)
    all_payments_dict = get_all_payments_by_tenant()
    
    defaulters = []
    raw_defaulters = []
    for _, row in tenants_df.iterrows():
        t_id = int(row['id'])
        t_payments = all_payments_dict.get(t_id, [])
        t_status = str(row['status'])
        t_end_date = row['end_date']
        unpaid_count, unpaid_names, _, _ = calculate_due_status_fast(str(row['start_date']), t_payments, t_status, t_end_date)
        
        if unpaid_count > 0 or status_filter == "العقود الملغاة / الموقوفة فقط":
            defaulters.append({
                "الاسم": row['name'],
                "الحالة": f"🔴 موقوف ({t_end_date})" if t_status == "ملغى / موقوف" else "🟢 نشط",
                "الهاتف": row['phone'],
                "أشهر التأخير": unpaid_count,
                "المبلغ المتأخر": unpaid_count * row['rent_price'],
                "الأشهر المعنية": "، ".join(unpaid_names) if unpaid_names else "لا توجد متأخرات"
            })
            raw_defaulters.append(row)
            
    if defaulters:
        st.dataframe(pd.DataFrame(defaulters), use_container_width=True)
    else:
        st.success("✅ لا توجد متأخرات مطابقة لهذا الفلتر.")

    # إتاحة اتخاذ الإجراءات (بما في ذلك إيقاف الكراء) لأي مكتري في القائمة المفلترة
    if role in ["SuperAdmin", "LocalAdmin"] and not tenants_df.empty:
        st.markdown("---")
        st.subheader("🛠️ إجراءات المتقاعسين وإيقاف الكراء (طلب الإلغاء / الإفراغ)")
        all_filtered_names = tenants_df['name'].tolist()
        selected_def_name = st.selectbox("اختر المكتري لاتخاذ الإجراء أو إيقاف الكراء:", options=all_filtered_names)
        
        if selected_def_name:
            s_row = tenants_df[tenants_df['name'] == selected_def_name].iloc[0]
            sel_id = int(s_row['id'])
            sel_phone = str(s_row['phone'])
            sel_status = str(s_row['status'])
            sel_end_date = s_row['end_date']
            
            t_payments = all_payments_dict.get(sel_id, [])
            u_cnt, u_nms, _, _ = calculate_due_status_fast(str(s_row['start_date']), t_payments, sel_status, sel_end_date)
            tot_debt = u_cnt * s_row['rent_price']
            months_str = "، ".join(u_nms)
            date_today = datetime.today().strftime("%Y-%m-%d")
            
            if sel_status == "ملغى / موقوف":
                st.error(f"🛑 **تنبيه:** الكراء موقوف حالياً لهذا المكتري ابتداءً من تاريخ **{sel_end_date}** (تم إيقاف احتساب أي أشهر جديدة بعد هذا التاريخ).")
            
            if sel_phone and sel_phone.lower() != 'nan' and sel_phone.strip() != '':
                p_clean = sel_phone.replace(" ", "").replace("+", "").replace("-", "")
                if p_clean.startswith("00212"): p_clean = p_clean[2:]
                elif p_clean.startswith("0"): p_clean = "212" + p_clean[1:]
                elif not p_clean.startswith("212"): p_clean = "212" + p_clean
                msg = f"السلام عليكم السيد(ة) {selected_def_name}، المرجو تسوية وضعية الكراء الخاص بالمحل. الشهور المتأخرة: {u_cnt} أشهر بمبلغ {tot_debt} درهم."
                st.markdown(f"**تواصل معه مباشرة:** [📱 إرسال رسالة تذكير عبر الواتساب](https://wa.me/{p_clean}?text={urllib.parse.quote(msg)})", unsafe_allow_html=True)
            else:
                st.warning("رقم الهاتف غير مسجل لهذا المكتري.")
            
            def create_word_notice(notice_type):
                if not HAS_DOCX: return None
                doc = Document()
                p_head = doc.add_paragraph()
                p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_head.add_run("المملكة المغربية\nالمجلس الجماعي لشراط\nمصلحة الممتلكات والمداخيل\n").bold = True
                p_date = doc.add_paragraph(f"التاريخ: {date_today}")
                p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p_to = doc.add_paragraph()
                p_to.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p_to.add_run(f"إلى السيد(ة): {selected_def_name}\n").bold = True
                p_to.add_run(f"العنوان: {s_row['address']}")
                
                p_sub = doc.add_paragraph()
                p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
                sub_text = "الموضوع: إنذار أول بتسوية وضعية الكراء" if notice_type == 1 else "الموضوع: إنذار ثاني وأخير قبل الإفراغ"
                run_sub = p_sub.add_run(f"\n{sub_text}\n")
                run_sub.bold = True
                run_sub.font.size = Pt(14)
                
                p_body = doc.add_paragraph()
                p_body.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p_body.add_run("سلام تام بوجود مولانا الإمام،\n\n")
                if notice_type == 1:
                    txt = f"وبعد، علاقة بالموضوع المشار إليه أعلاه، ننهي إلى علمكم أنكم مدينون بمبلغ {tot_debt} درهم، وهو ما يمثل واجب كراء المحل لمدة {u_cnt} أشهر ({months_str}).\nلذا، نطلب منكم تسوية هذه الوضعية لدى المصالح المالية في أجل أقصاه 15 يوماً من تاريخ التوصل بهذا الإنذار.\n\nوفي حالة عدم الاستجابة، ستتخذ الإدارة الإجراءات القانونية الجاري بها العمل.\n\nوالسلام."
                else:
                    txt = f"إلحاقاً بإنذارنا الأول، ونظراً لعدم تسويتكم لوضعيتكم المادية حيث تبلغ ديونكم {tot_debt} درهم عن مدة {u_cnt} أشهر ({months_str}).\nفإننا نوجه لكم هذا الإنذار الثاني والأخير لتسوية وضعيتكم خلال 8 أيام.\nوفي حال الاستمرار في التماطل، سنضطر آسفين لاتخاذ الإجراءات القانونية لفسخ العقد والإفراغ.\n\nوالسلام."
                p_body.add_run(txt)
                p_sign = doc.add_paragraph("\n\nالتوقيع:")
                p_sign.alignment = WD_ALIGN_PARAGRAPH.LEFT
                bio = io.BytesIO()
                doc.save(bio)
                return bio.getvalue()
            
            st.markdown("### 📝 توليد وطباعة الإنذارات (بصيغة Word)")
            word_n1 = create_word_notice(1)
            word_n2 = create_word_notice(2)
            
            col_gen1, col_gen2 = st.columns(2)
            with col_gen1:
                if word_n1:
                    st.download_button("📥 تحميل الإنذار الأول (Word)", data=word_n1, file_name=f"إنذار_أول_{selected_def_name}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            with col_gen2:
                if word_n2:
                    st.download_button("📥 تحميل الإنذار الثاني (Word)", data=word_n2, file_name=f"إنذار_ثاني_{selected_def_name}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

            c.execute("SELECT notice_1_filename, notice_2_filename, cancellation_filename FROM tenants WHERE id = %s", (sel_id,))
            f_res = c.fetchone()
            
            st.markdown("### 📁 أرشفة الإنذارات وطلب الإلغاء (مع إيقاف الكراء)")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**الإنذار الأول**")
                if f_res and f_res[0]: st.success(f"مرفوع: {f_res[0]}")
                with st.form("form_n1", clear_on_submit=True):
                    f1 = st.file_uploader("ملف الإنذار الأول", type=["pdf", "png", "jpg"], key="n1")
                    if st.form_submit_button("حفظ") and f1:
                        fb, fn = get_file_data(f1)
                        c.execute("UPDATE tenants SET notice_1_file = %s, notice_1_filename = %s WHERE id = %s", (fb, fn, sel_id))
                        clear_app_cache()
                        st.success("تم الرفع!"); st.rerun()
            with col2:
                st.markdown("**الإنذار الثاني**")
                if f_res and f_res[1]: st.success(f"مرفوع: {f_res[1]}")
                with st.form("form_n2", clear_on_submit=True):
                    f2 = st.file_uploader("ملف الإنذار الثاني", type=["pdf", "png", "jpg"], key="n2")
                    if st.form_submit_button("حفظ") and f2:
                        fb, fn = get_file_data(f2)
                        c.execute("UPDATE tenants SET notice_2_file = %s, notice_2_filename = %s WHERE id = %s", (fb, fn, sel_id))
                        clear_app_cache()
                        st.success("تم الرفع!"); st.rerun()
            with col3:
                st.markdown("**🛑 طلب الإلغاء / الإفراغ (إيقاف الكراء)**")
                if f_res and f_res[2]: st.success(f"مرفوع: {f_res[2]}")
                with st.form("form_c", clear_on_submit=True):
                    default_cancel_d = datetime.today().date()
                    if sel_end_date and str(sel_end_date).strip() not in ("", "None", "nan"):
                        try:
                            default_cancel_d = datetime.strptime(str(sel_end_date).strip(), "%Y-%m-%d").date()
                        except Exception:
                            pass
                    cancel_date = st.date_input("تاريخ إيقاف/إلغاء الكراء:", value=default_cancel_d)
                    fc = st.file_uploader("نسخة طلب الإلغاء (اختياري)", type=["pdf", "png", "jpg"], key="nc")
                    if st.form_submit_button("🛑 تأكيد إيقاف الكراء وحفظ الطلب"):
                        if fc:
                            fb, fn = get_file_data(fc)
                            c.execute(
                                "UPDATE tenants SET status = 'ملغى / موقوف', end_date = %s, cancellation_file = %s, cancellation_filename = %s WHERE id = %s",
                                (str(cancel_date), fb, fn, sel_id)
                            )
                        else:
                            c.execute(
                                "UPDATE tenants SET status = 'ملغى / موقوف', end_date = %s WHERE id = %s",
                                (str(cancel_date), sel_id)
                            )
                        clear_app_cache()
                        st.success(f"✅ تم إيقاف الكراء بنجاح ابتداءً من {cancel_date}!")
                        st.rerun()

# ---------------------------------------------------------
# الواجهة 5: البحث والتصفية
# ---------------------------------------------------------
elif active_tab == "🔍 البحث والتصفية":
    st.subheader("البحث عن مكتري وعرض التفاصيل، الديون، والمرفقات")
    selected_search_cat = st.selectbox("🏷️ فلترة القائمة حسب الصنف لسرعة البحث:", options=["الكل"] + category_options, key="search_cat_filter")
    
    if selected_search_cat == "الكل":
        all_tenants_df = run_query("SELECT id, name, cin, shop_category, COALESCE(status, 'نشط') AS status FROM tenants ORDER BY name ASC")
    else:
        all_tenants_df = run_query("SELECT id, name, cin, shop_category, COALESCE(status, 'نشط') AS status FROM tenants WHERE shop_category = %s ORDER BY name ASC", (selected_search_cat,))
    
    if not all_tenants_df.empty:
        options = [""] + [
            f"{row['name']} ({'موقوف' if row['status'] == 'ملغى / موقوف' else 'نشط'}) - (بطاقة: {row['cin'] if row['cin'] else 'غير متوفر'}) - [ID: {row['id']}]"
            for _, row in all_tenants_df.iterrows()
        ]
        selected_option = st.selectbox("🔍 ابدأ بكتابة اسم المكتري (ستظهر النتائج فوراً):", options=options)
        
        if selected_option:
            t_id = int(selected_option.split("[ID: ")[1].replace("]", ""))
            
            df_search = run_query("""
                SELECT id, name, cin, phone, address, shop_category, start_date, rent_price, contract_id, 
                       COALESCE(status, 'نشط') AS status, end_date,
                       id_card_filename, contract_filename, conditions_filename, notice_1_filename, notice_2_filename, cancellation_filename 
                FROM tenants WHERE id = %s
            """, (t_id,))
            
            if not df_search.empty:
                row = df_search.iloc[0]
                t_status = str(row['status'])
                t_end_date = row['end_date']
                
                if t_status == "ملغى / موقوف":
                    st.error(f"🛑 **حالة العقد:** ملغى / موقوف (توقف احتساب الكراء بتاريخ: **{t_end_date}**)")
                else:
                    st.success("🟢 **حالة العقد:** نشط ومستمر")
                    
                with st.expander(f"👤 البيانات الأساسية لـ: {row['name']}", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**الاسم الكامل:** {row['name']}")
                        st.write(f"**رقم البطاقة (CIN):** {row.get('cin', 'غير متوفر')}")
                        st.write(f"**رقم الهاتف:** {row.get('phone', 'غير متوفر')}")
                        st.write(f"**العنوان / المحل:** {row.get('address', 'غير متوفر')}")
                        st.write(f"**الصنف:** {row.get('shop_category', 'غير محدد')}")
                    with col2:
                        st.write(f"**تاريخ بداية الكراء:** {row.get('start_date', 'غير متوفر')}")
                        if t_status == "ملغى / موقوف":
                            st.write(f"**تاريخ إيقاف الكراء:** {t_end_date if t_end_date else 'غير محدد'}")
                        st.write(f"**ثمن الكراء الشهري:** {row.get('rent_price', 0)} درهم")
                        st.write(f"**رقم العقد:** {row.get('contract_id', 'غير متوفر')}")
                
                st.markdown("### 💰 الوضعية المالية (الأداءات والديون)")
                p_df = run_query("SELECT paid_months_names, months_paid FROM payments WHERE tenant_id = %s", (t_id,))
                tenant_payments = list(zip(p_df['paid_months_names'], p_df['months_paid'])) if not p_df.empty else []
                u_cnt, u_nms, _, p_months = calculate_due_status_fast(str(row['start_date']), tenant_payments, t_status, t_end_date)
                
                c_stat1, c_stat2 = st.columns(2)
                with c_stat1:
                    st.info(f"**إجمالي الأشهر المؤداة:** {p_months} أشهر")
                    payments_df = run_query("SELECT id, amount, payment_date, paid_months_names, receipt_filename FROM payments WHERE tenant_id = %s ORDER BY id DESC", (t_id,))
                    if not payments_df.empty:
                        st.write("**تاريخ الأداءات ووصولات الدفع:**")
                        for p_idx, p_row in payments_df.iterrows():
                            p_id = int(p_row['id'])
                            with st.expander(f"📅 دفعة بتاريخ {p_row['payment_date']} | مبلغ {p_row['amount']} درهم"):
                                st.write(f"**الأشهر التي تم أداؤها:** {p_row['paid_months_names']}")
                                if pd.notna(p_row.get('receipt_filename')) and str(p_row.get('receipt_filename')).strip() != '':
                                    r_bytes, r_filename = get_receipt_bytes(p_id)
                                    if r_bytes:
                                        st.download_button(
                                            label=f"📥 تحميل وصل الأداء ({r_filename})", 
                                            data=r_bytes, 
                                            file_name=r_filename, 
                                            key=f"rec_dl_{t_id}_{p_id}_{p_idx}"
                                        )
                                    else:
                                        st.warning("الملف المرفق غير متوفر في قاعدة البيانات.")
                                else:
                                    st.warning("لا يوجد وصل مرفق لهذه العملية.")
                    else:
                        st.write("لم يتم تسجيل أي أداءات حتى الآن.")

                with c_stat2:
                    if u_cnt > 0:
                        st.error(f"**إجمالي الأشهر المتأخرة{' (قبل الإيقاف)' if t_status == 'ملغى / موقوف' else ''}:** {u_cnt} أشهر")
                        st.write(f"**الديون المتراكمة:** {u_cnt * row['rent_price']} درهم")
                        st.write(f"**تفصيل الأشهر غير المؤداة:** {'، '.join(u_nms)}")
                    else:
                        st.success("✅ الوضعية المالية مصفاة، لا توجد ديون متأخرة!")

                st.markdown("### 📁 الوثائق والمرفقات الأساسية")
                doc_fields = [
                    ("id_card_file", "id_card_filename", "البطاقة الوطنية"),
                    ("contract_file", "contract_filename", "عقد الكراء"),
                    ("conditions_file", "conditions_filename", "كناش التحملات"),
                    ("notice_1_file", "notice_1_filename", "الإنذار الأول"),
                    ("notice_2_file", "notice_2_filename", "الإنذار الثاني"),
                    ("cancellation_file", "cancellation_filename", "طلب الإلغاء / الإفراغ")
                ]
                
                doc_cols = st.columns(3)
                found_doc_count = 0
                for f_col, n_col, label in doc_fields:
                    fname = row.get(n_col)
                    if pd.notna(fname) and str(fname).strip() != '':
                        fbytes, real_fname = get_tenant_file(t_id, f_col, n_col)
                        if fbytes:
                            with doc_cols[found_doc_count % 3]:
                                st.download_button(
                                    label=f"📥 {label} ({real_fname})",
                                    data=fbytes,
                                    file_name=real_fname,
                                    key=f"dl_tenant_doc_{t_id}_{f_col}"
                                )
                            found_doc_count += 1
                
                if found_doc_count == 0:
                    st.info("لا توجد وثائق أساسية مسجلة لهذا المكتري.")

# ---------------------------------------------------------
# الواجهة 6: تصحيح وتعديل الأخطاء
# ---------------------------------------------------------
elif active_tab == "🗑️ تصحيح الأخطاء":
    st.subheader("🛠️ تصحيح الأخطاء: تعديل أو إلغاء عمليات الأداء")
    df_recent = run_query("SELECT id AS \"رقم العملية\", tenant_name AS \"اسم المكتري\", amount AS \"المبلغ\", payment_date AS \"تاريخ الأداء\", paid_months_names AS \"الأشهر المستخلصة\", receipt_filename AS \"الملف المرفق\" FROM payments ORDER BY id DESC LIMIT 30")
    
    if not df_recent.empty:
        st.dataframe(df_recent, use_container_width=True)
        action_type = st.radio("اختر نوع الإجراء المطلوب:", ["✏️ تعديل عملية أداء (تاريخ / الشهر المستخلص / وصل / موظف)", "🗑️ حذف عملية أداء"], horizontal=True)

        if action_type == "✏️ تعديل عملية أداء (تاريخ / الشهر المستخلص / وصل / موظف)":
            st.markdown("---")
            pay_options = {f"عملية رقم #{row['رقم العملية']} - {row['اسم المكتري']} ({row['الأشهر المستخلصة']} - بتاريخ {row['تاريخ الأداء']})": int(row['رقم العملية']) for _, row in df_recent.iterrows()}
            selected_pay_label = st.selectbox("اختر العملية المراد تعديلها:", options=list(pay_options.keys()))

            if selected_pay_label:
                selected_pid = pay_options[selected_pay_label]
                c.execute("SELECT payment_date, receipt_filename, amount, employee, paid_months_names FROM payments WHERE id = %s", (selected_pid,))
                p_data = c.fetchone()

                if p_data:
                    curr_date_str, curr_filename, curr_amount, curr_emp, curr_months_names = p_data
                    try:
                        curr_d = datetime.strptime(str(curr_date_str), "%Y-%m-%d").date()
                    except Exception:
                        curr_d = datetime.today().date()

                    with st.form("edit_payment_form"):
                        st.info(f"📍 تعديل بيانات العملية رقم: **{selected_pid}** | المبلغ: **{curr_amount} درهم**")
                        col_p1, col_p2 = st.columns(2)
                        with col_p1:
                            new_pay_date = st.date_input("تحديث تاريخ العملية / الأداء:", value=curr_d)
                            new_months_names = st.text_input("تحديث الشهر المستخلص (مثال: أبريل 2026):", value=curr_months_names if curr_months_names else "")
                            new_employee = st.text_input("تحديث اسم الموظف المستخلص:", value=curr_emp if curr_emp else "")

                        with col_p2:
                            st.caption(f"📁 الملف المرفق الحالي: `{curr_filename}`" if curr_filename else "📁 لا يوجد ملف مرفق حالياً.")
                            new_receipt_file = st.file_uploader("رفع وصل جديد (استبدال الوصل الحالي):", type=["pdf", "png", "jpg", "jpeg"], key=f"edit_rec_{selected_pid}")

                        if st.form_submit_button("💾 حفظ تعديلات عملية الأداء"):
                            if new_receipt_file is not None:
                                r_bytes, r_name = get_file_data(new_receipt_file)
                                c.execute("UPDATE payments SET payment_date = %s, paid_months_names = %s, employee = %s, receipt_file = %s, receipt_filename = %s WHERE id = %s", (str(new_pay_date), new_months_names, new_employee, r_bytes, r_name, selected_pid))
                            else:
                                c.execute("UPDATE payments SET payment_date = %s, paid_months_names = %s, employee = %s WHERE id = %s", (str(new_pay_date), new_months_names, new_employee, selected_pid))

                            clear_app_cache()
                            st.success(f"✅ تم تحديث بيانات العملية رقم {selected_pid} بنجاح!")
                            st.rerun()
        else:
            st.markdown("---")
            pid = st.number_input("أدخل رقم العملية المراد حذفها:", min_value=0, step=1, value=0)
            if st.button("🗑️ تأكيد حذف العملية"):
                if pid > 0:
                    c.execute("DELETE FROM payments WHERE id = %s", (int(pid),))
                    clear_app_cache()
                    st.success("✅ تم حذف العملية بنجاح!")
                    st.rerun()
                else:
                    st.warning("المرجو إدخال رقم عملية صحيح.")

# ---------------------------------------------------------
# الواجهة 7: إدارة وتعديل المكترين (بما في ذلك إيقاف أو إعادة تفعيل الكراء)
# ---------------------------------------------------------
elif active_tab == "⚙️ إدارة المكترين":
    st.subheader("⚙️ إدارة وتعديل المكترين، التواريخ، وحالة إيقاف الكراء")
    with st.expander("🛠️ أداة دمج وتوحيد الأصناف المتشابهة (مثال: دمج 'صنف 1' مع 'محلات صنف 1')"):
        st.write("استخدم هذه الأداة لتحويل كافة المكترين المسجلين تحت صنف معّين إلى صنف آخر بضغطة زر:")
        col_m1, col_m2, col_m3 = st.columns(3)
        all_db_cats = run_query("SELECT DISTINCT shop_category FROM tenants WHERE shop_category IS NOT NULL AND shop_category != ''")
        existing_cats_list = all_db_cats['shop_category'].tolist() if not all_db_cats.empty else category_options
        
        from_cat = col_m1.selectbox("الصنف المراد تغييره / دمجه:", options=existing_cats_list, key="from_cat_key")
        to_cat = col_m2.selectbox("التحويل إلى الصنف الموحد:", options=category_options, key="to_cat_key")
        if col_m3.button("🔄 دمج وتوحيد الأصناف الآن"):
            if from_cat and to_cat:
                c.execute("UPDATE tenants SET shop_category = %s WHERE shop_category = %s;", (to_cat, from_cat))
                clear_app_cache()
                st.success(f"✅ تم تحويل جميع المحلات المسجلة في '{from_cat}' إلى '{to_cat}' بنجاح!")
                st.rerun()

    st.markdown("---")
    selected_edit_cat = st.selectbox("🏷️ فلترة القائمة حسب الصنف لسرعة التعديل والتركيز:", options=["الكل"] + category_options, key="edit_cat_filter")
    edit_mode = st.radio("اختر طريقة التعديل:", ["✏️ تعديل فردي (مكتري واحد)", "📊 تعديل جماعي (جدول تفاعلي / Excel)"], horizontal=True)
    
    if selected_edit_cat == "الكل":
        tenants_edit_df = run_query("SELECT id, name, contract_id, cin, address, phone, rent_price, shop_category, start_date, COALESCE(status, 'نشط') AS status, COALESCE(end_date, '') AS end_date FROM tenants ORDER BY id ASC")
    else:
        tenants_edit_df = run_query("SELECT id, name, contract_id, cin, address, phone, rent_price, shop_category, start_date, COALESCE(status, 'نشط') AS status, COALESCE(end_date, '') AS end_date FROM tenants WHERE shop_category = %s ORDER BY id ASC", (selected_edit_cat,))
    
    if not tenants_edit_df.empty:
        if edit_mode == "✏️ تعديل فردي (مكتري واحد)":
            edit_dict = dict(zip(tenants_edit_df['name'], tenants_edit_df['id']))
            selected_edit_tenant = st.selectbox("اختر المكتري للتعديل:", options=list(edit_dict.keys()))
            t_edit_id = int(edit_dict[selected_edit_tenant])
            
            c.execute("SELECT phone, shop_category, rent_price, start_date, address, cin, contract_id, COALESCE(status, 'نشط'), end_date FROM tenants WHERE id = %s", (t_edit_id,))
            res_tenant = c.fetchone()
            if res_tenant:
                try:
                    curr_start_d = datetime.strptime(str(res_tenant[3]), "%Y-%m-%d").date()
                except Exception:
                    curr_start_d = datetime.today().date()
                    
                curr_end_d = datetime.today().date()
                if res_tenant[8] and str(res_tenant[8]).strip() not in ("", "None", "nan"):
                    try:
                        curr_end_d = datetime.strptime(str(res_tenant[8]).strip(), "%Y-%m-%d").date()
                    except Exception:
                        pass
                    
                with st.form("edit_form_single"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_contract = st.text_input("تحديث رقم عقد الكراء:", value=res_tenant[6] if res_tenant[6] else "")
                        new_cin = st.text_input("تحديث رقم البطاقة الوطنية (CIN):", value=res_tenant[5] if res_tenant[5] else "")
                        new_phone = st.text_input("تحديث الهاتف:", value=res_tenant[0] if res_tenant[0] else "")
                        new_start_date = st.date_input("تحديث تاريخ بداية الكراء:", value=curr_start_d)
                    with c2:
                        new_address = st.text_input("تحديث العنوان / رقم المحل:", value=res_tenant[4] if res_tenant[4] else "")
                        new_rent = st.number_input("تحديث ثمن الكراء الشهري:", value=float(res_tenant[2]) if res_tenant[2] else 0.0)
                        curr_cat = normalize_category_name(res_tenant[1])
                        curr_cat_idx = category_options.index(curr_cat) if curr_cat in category_options else 0
                        new_category = st.selectbox("تحديث الصنف:", options=category_options, index=curr_cat_idx)
                        
                        status_opts = ["نشط", "ملغى / موقوف"]
                        curr_st_idx = status_opts.index(res_tenant[7]) if res_tenant[7] in status_opts else 0
                        new_status = st.selectbox("حالة العقد (اختر 'ملغى / موقوف' لإيقاف الكراء):", options=status_opts, index=curr_st_idx)
                        new_end_date = st.date_input("تاريخ إيقاف/إلغاء الكراء (يُعتمد عند الإلغاء):", value=curr_end_d)
                    
                    if st.form_submit_button("💾 حفظ التعديلات الفردية"):
                        final_end_date = str(new_end_date) if new_status == "ملغى / موقوف" else ""
                        c.execute("UPDATE tenants SET contract_id = %s, cin = %s, address = %s, phone = %s, rent_price = %s, shop_category = %s, start_date = %s, status = %s, end_date = %s WHERE id = %s",
                                  (new_contract, new_cin, new_address, new_phone, new_rent, new_category, str(new_start_date), new_status, final_end_date, t_edit_id))
                        clear_app_cache()
                        st.success("✅ تم تحديث بيانات المكتري وحالة الكراء بنجاح!")
                        st.rerun()
        else:
            st.info("💡 يمكنك تغيير عمود **حالة الكراء** إلى `ملغى / موقوف` وتحديد **تاريخ الإيقاف** مباشرة لعدة مكترين دفعة واحدة ثم الضغط على حفظ:")
            edited_df = st.data_editor(
                tenants_edit_df,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "name": "اسم المكتري",
                    "contract_id": "رقم العقد",
                    "cin": "رقم البطاقة",
                    "address": "العنوان / رقم المحل",
                    "phone": "رقم الهاتف",
                    "rent_price": "ثمن الكراء",
                    "shop_category": "الصنف",
                    "start_date": "تاريخ البداية",
                    "status": st.column_config.SelectboxColumn("حالة الكراء", options=["نشط", "ملغى / موقوف"], required=True),
                    "end_date": "تاريخ الإيقاف (YYYY-MM-DD)"
                },
                disabled=["id"], use_container_width=True, num_rows="fixed", key=f"bulk_tenant_editor_{selected_edit_cat}"
            )
            if st.button("💾 حفظ التعديلات الجماعية من الجدول"):
                for _, row in edited_df.iterrows():
                    row_status = str(row['status']).strip() if pd.notna(row['status']) else 'نشط'
                    row_end = str(row['end_date']).strip() if pd.notna(row['end_date']) else ''
                    if row_status == "ملغى / موقوف" and not row_end:
                        row_end = datetime.today().strftime("%Y-%m-%d")
                    elif row_status == "نشط":
                        row_end = ""
                        
                    c.execute("UPDATE tenants SET contract_id = %s, name = %s, cin = %s, address = %s, phone = %s, rent_price = %s, shop_category = %s, start_date = %s, status = %s, end_date = %s WHERE id = %s",
                              (
                                  str(row['contract_id']) if pd.notna(row['contract_id']) else '',
                                  str(row['name']),
                                  str(row['cin']) if pd.notna(row['cin']) else '',
                                  str(row['address']) if pd.notna(row['address']) else '',
                                  str(row['phone']) if pd.notna(row['phone']) else '',
                                  float(row['rent_price']) if pd.notna(row['rent_price']) else 0.0,
                                  normalize_category_name(row['shop_category']),
                                  str(row['start_date']) if pd.notna(row['start_date']) else str(datetime.today().date()),
                                  row_status,
                                  row_end,
                                  int(row['id'])
                              ))
                clear_app_cache()
                st.success("✅ تم حفظ التعديلات الجماعية بنجاح!")
                st.rerun()

# ---------------------------------------------------------
# الواجهة 8: النسخ الاحتياطي
# ---------------------------------------------------------
elif active_tab == "💾 النسخ الاحتياطي":
    st.subheader("💾 النسخ الاحتياطي والتقرير التفصيلي وحصر المحلات الشاغرة")
    tenants_all_df = run_query("SELECT id, name, cin, address, shop_category, rent_price, start_date, COALESCE(status, 'نشط') AS status, end_date FROM tenants ORDER BY shop_category ASC, id ASC")
    all_payments_dict = get_all_payments_by_tenant()

    if not tenants_all_df.empty:
        backup_data = []
        vacant_summary = []
        month_names_ar = ["يناير", "فبراير", "مارس", "أبريل", "ماي", "يونيو", "يوليوز", "غشت", "شتنبر", "أكتوبر", "نونبر", "دجنبر"]

        for _, row in tenants_all_df.iterrows():
            t_id = int(row['id'])
            s_date_str = str(row['start_date'])
            rent = float(row['rent_price']) if pd.notna(row['rent_price']) else 0.0
            category = normalize_category_name(row['shop_category'])
            t_status = str(row['status'])
            t_end_date = row['end_date']
            
            raw_address = str(row['address']) if pd.notna(row['address']) else "غير متوفر"
            clean_shop = raw_address
            if category != "غير محدد" and category in clean_shop:
                clean_shop = clean_shop.replace(category, "").strip(" -_:")
            if not clean_shop:
                clean_shop = raw_address

            t_payments = all_payments_dict.get(t_id, [])
            unpaid_count, unpaid_names, _, paid_count = calculate_due_status_fast(s_date_str, t_payments, t_status, t_end_date)

            if paid_count > 0:
                try:
                    s_dt = datetime.strptime(s_date_str, "%Y-%m-%d").date()
                    last_paid_dt = s_dt + relativedelta(months=int(paid_count) - 1)
                    last_paid_str = f"{month_names_ar[last_paid_dt.month - 1]} {last_paid_dt.year}"
                except Exception:
                    last_paid_str = "غير معروف"
            else:
                last_paid_str = "لم يتم الأداء بعد"

            status_label = f"موقوف ({t_end_date})" if t_status == "ملغى / موقوف" else "نشط"

            backup_data.append({
                "الصنف": category,
                "اسم المكتري": row['name'],
                "حالة العقد": status_label,
                "رقم البطاقة": row['cin'] if pd.notna(row['cin']) and str(row['cin']).strip() != '' else "غير متوفر",
                "رقم المحل": clean_shop,
                "ثمن الكراء (درهم)": rent,
                "الأشهر المؤداة": paid_count,
                "الأشهر الغير مؤداة": unpaid_count,
                "آخر شهر تم أداؤه": last_paid_str,
                "المبالغ الغير مستخلصة (درهم)": unpaid_count * rent
            })

        full_backup_df = pd.DataFrame(backup_data)
        grouped_shops = full_backup_df.groupby("الصنف")

        for cat_name, group in grouped_shops:
            all_cat_nums = []
            active_shop_numbers = []
            for _, g_row in group.iterrows():
                digits = re.findall(r'\d+', str(g_row["رقم المحل"]))
                if digits:
                    num = int(digits[0])
                    all_cat_nums.append(num)
                    # المحلات النشطة فقط تُعتبر مشغولة، أما الموقوفة فتعود شاغرة
                    if g_row["حالة العقد"] == "نشط":
                        active_shop_numbers.append(num)
            
            if all_cat_nums:
                max_num = max(all_cat_nums)
                occupied_set = set(active_shop_numbers)
                vacant_nums = sorted(list(set(range(1, max_num + 1)) - occupied_set))
                vacant_str = "، ".join(map(str, vacant_nums)) if vacant_nums else "لا توجد محلات شاغرة (جميع المحلات نشطة ومكتراة)"
                vacant_count = len(vacant_nums)
            else:
                vacant_str = "غير محدد"
                vacant_count = 0

            vacant_summary.append({"الصنف": cat_name, "أرقام المحلات الشاغرة (غير المكتراة أو الملغاة)": vacant_str, "عدد المحلات الشاغرة": vacant_count})

        vacant_df = pd.DataFrame(vacant_summary)
        st.markdown("### 🏢 قائمة المحلات الشاغرة / الفارغة حسب الأصناف")
        st.dataframe(vacant_df, use_container_width=True)
        st.markdown("---")
        st.markdown("### 📊 السجل الشامل للمكترين")
        st.dataframe(full_backup_df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            header_fmt = workbook.add_format({'border': 1, 'bold': True, 'bg_color': '#1F4E79', 'font_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter', 'font_size': 11})
            cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 10})
            total_fmt = workbook.add_format({'border': 1, 'bold': True, 'bg_color': '#D9E1F2', 'font_color': '#000000', 'align': 'center', 'valign': 'vcenter', 'font_size': 11})
            vacant_fmt = workbook.add_format({'border': 1, 'bold': True, 'bg_color': '#FCE4D6', 'font_color': '#C65911', 'align': 'center', 'valign': 'vcenter', 'font_size': 11})

            vacant_df.to_excel(writer, index=False, sheet_name="المحلات الشاغرة")
            ws_v = writer.sheets["المحلات الشاغرة"]
            ws_v.right_to_left()
            ws_v.hide_gridlines(0)
            ws_v.set_row(0, 25)
            for c_idx, c_name in enumerate(vacant_df.columns):
                ws_v.write(0, c_idx, c_name, header_fmt)
            for r_idx in range(len(vacant_df)):
                ws_v.set_row(r_idx + 1, 22)
                for c_idx in range(len(vacant_df.columns)):
                    ws_v.write(r_idx + 1, c_idx, vacant_df.iloc[r_idx, c_idx], vacant_fmt)
            ws_v.set_column(0, 0, 20)
            ws_v.set_column(1, 1, 45)
            ws_v.set_column(2, 2, 20)

            for cat_name, group in grouped_shops:
                sheet_title = str(cat_name).replace("/", "-").replace("\\", "-")[:30]
                cat_df = group.drop(columns=["الصنف"])
                tot_rent = cat_df["ثمن الكراء (درهم)"].sum()
                tot_paid = cat_df["الأشهر المؤداة"].sum()
                tot_unpaid = cat_df["الأشهر الغير مؤداة"].sum()
                tot_debt = cat_df["المبالغ الغير مستخلصة (درهم)"].sum()

                total_row = pd.DataFrame([{
                    "اسم المكتري": "المجموع الإجمالي",
                    "حالة العقد": "---",
                    "رقم البطاقة": "---",
                    "رقم المحل": "---",
                    "ثمن الكراء (درهم)": tot_rent,
                    "الأشهر المؤداة": tot_paid,
                    "الأشهر الغير مؤداة": tot_unpaid,
                    "آخر شهر تم أداؤه": "---",
                    "المبالغ الغير مستخلصة (درهم)": tot_debt
                }])
                cat_df_display = pd.concat([cat_df, total_row], ignore_index=True)
                cat_df_display.to_excel(writer, index=False, sheet_name=sheet_title)

                ws = writer.sheets[sheet_title]
                ws.right_to_left()
                ws.hide_gridlines(0)
                ws.set_row(0, 25)
                for c_idx, c_name in enumerate(cat_df_display.columns):
                    ws.write(0, c_idx, c_name, header_fmt)

                for r_idx in range(len(cat_df_display)):
                    ws.set_row(r_idx + 1, 22)
                    is_tot = (r_idx == len(cat_df_display) - 1)
                    f = total_fmt if is_tot else cell_fmt
                    for c_idx in range(len(cat_df_display.columns)):
                        ws.write(r_idx + 1, c_idx, cat_df_display.iloc[r_idx, c_idx], f)

                v_row = vacant_df[vacant_df["الصنف"] == cat_name]
                if not v_row.empty:
                    v_str = v_row.iloc[0]["أرقام المحلات الشاغرة (غير المكتراة أو الملغاة)"]
                    v_row_idx = len(cat_df_display) + 2
                    ws.merge_range(v_row_idx, 0, v_row_idx, 2, "أرقام المحلات الشاغرة (الخالية):", vacant_fmt)
                    ws.merge_range(v_row_idx, 3, v_row_idx, 8, v_str, cell_fmt)

                widths = [24, 18, 15, 12, 16, 14, 15, 18, 22]
                for idx, w in enumerate(widths):
                    ws.set_column(idx, idx, w)

            all_sheet_df = full_backup_df.copy()
            tot_rent_all = all_sheet_df["ثمن الكراء (درهم)"].sum()
            tot_paid_all = all_sheet_df["الأشهر المؤداة"].sum()
            tot_unpaid_all = all_sheet_df["الأشهر الغير مؤداة"].sum()
            tot_debt_all = all_sheet_df["المبالغ الغير مستخلصة (درهم)"].sum()

            tot_all_row = pd.DataFrame([{
                "الصنف": "المجموع الشامل",
                "اسم المكتري": "---",
                "حالة العقد": "---",
                "رقم البطاقة": "---",
                "رقم المحل": "---",
                "ثمن الكراء (درهم)": tot_rent_all,
                "الأشهر المؤداة": tot_paid_all,
                "الأشهر الغير مؤداة": tot_unpaid_all,
                "آخر شهر تم أداؤه": "---",
                "المبالغ الغير مستخلصة (درهم)": tot_debt_all
            }])
            all_sheet_df_display = pd.concat([all_sheet_df, tot_all_row], ignore_index=True)
            all_sheet_df_display.to_excel(writer, index=False, sheet_name="التقرير الشامل")
            
            ws_all = writer.sheets["التقرير الشامل"]
            ws_all.right_to_left()
            ws_all.hide_gridlines(0)
            ws_all.set_row(0, 25)
            for c_idx, c_name in enumerate(all_sheet_df_display.columns):
                ws_all.write(0, c_idx, c_name, header_fmt)
            for r_idx in range(len(all_sheet_df_display)):
                ws_all.set_row(r_idx + 1, 22)
                is_tot = (r_idx == len(all_sheet_df_display) - 1)
                f = total_fmt if is_tot else cell_fmt
                for c_idx in range(len(all_sheet_df_display.columns)):
                    ws_all.write(r_idx + 1, c_idx, all_sheet_df_display.iloc[r_idx, c_idx], f)

            all_widths = [16, 24, 18, 15, 12, 16, 14, 15, 18, 22]
            for idx, w in enumerate(all_widths):
                ws_all.set_column(idx, idx, w)

        st.download_button(
            "📥 تحميل ملف النسخ الاحتياطي التفصيلي وحصر المحلات الشاغرة",
            data=output.getvalue(),
            file_name="النسخ_الاحتياطي_الشامل_مع_المحلات_الشاغرة.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
