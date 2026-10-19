import streamlit as st
import psycopg2
import urllib.parse
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
io = __import__('io')

# إعداد الصفحة
st.set_page_config(page_title="برنامج كراء المحلات", layout="wide", page_icon="🏢")

# 1. نظام تسجيل الدخول مع تحديد صلاحيات دقيقة لكل مشرف
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""

if not st.session_state["authenticated"]:
    st.title("🔐 تسجيل الدخول إلى نظام المحلات")
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

with st.sidebar:
    st.write(f"👤 المستخدم: **{st.session_state['username']}**")
    st.write(f"🛡️ الصلاحية: **{st.session_state['role']}**")
    if st.button("تسجيل الخروج"):
        st.session_state["authenticated"] = False
        st.rerun()

# 2. إعداد الاتصال بقاعدة البيانات السحابية
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

def get_file_data(uploaded_file):
    if uploaded_file is not None:
        return uploaded_file.getvalue(), uploaded_file.name
    return None, None

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

c = conn.cursor()

# إنشاء الجداول
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

for col_name in ["notice_1_file BYTEA", "notice_1_filename TEXT", "notice_2_file BYTEA", "notice_2_filename TEXT", "cancellation_file BYTEA", "cancellation_filename TEXT"]:
    try:
        c.execute(f"ALTER TABLE tenants ADD COLUMN IF NOT EXISTS {col_name};")
    except:
        pass

c.execute("""CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY, 
    tenant_id INTEGER, tenant_name TEXT,
    months_paid INTEGER, amount REAL, payment_date TEXT, employee TEXT, paid_months_names TEXT, 
    receipt_file BYTEA, receipt_filename TEXT
)""")

st.title("🏢 نظام تسيير كراء المحلات التجاري")

# تخصيص الألسنة بناءً على الصلاحية
role = st.session_state["role"]

if role == "SuperAdmin":
    tab_names = ["➕ إضافة مكتري", "💰 تسجيل أداء", "🏦 تقرير البنك", "⚖️ المتقاعسون", "🔍 البحث", "🗑️ تصحيح الأخطاء", "⚙️ إدارة المكترين", "💾 النسخ الاحتياطي"]
    tabs = st.tabs(tab_names)
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7]
elif role == "FinanceAdmin":
    tabs = st.tabs(["💰 تسجيل أداء", "🏦 تقرير البنك", "🔍 البحث"])
    t2, t3, t5 = tabs[0], tabs[1], tabs[2]
    t1 = t4 = t6 = t7 = t8 = None
elif role == "LocalAdmin":
    tabs = st.tabs(["➕ إضافة مكتري", "⚖️ المتقاعسون", "🔍 البحث", "⚙️ إدارة المكترين"])
    t1, t4, t5, t7 = tabs[0], tabs[1], tabs[2], tabs[3]
    t2 = t3 = t6 = t8 = None
else:
    tabs = st.tabs(["🔍 البحث", "🏦 تقرير البنك", "⚖️ المتقاعسون"])
    t5, t3, t4 = tabs[0], tabs[1], tabs[2]
    t1 = t2 = t6 = t7 = t8 = None

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

default_categories = ["بيع الدواجن", "بيع اللحوم", "المطاعم", "محلات صنف 1", "محلات صنف 2", "أصناف أخرى"]
try:
    cat_df = run_query("SELECT DISTINCT shop_category FROM tenants WHERE shop_category IS NOT NULL")
    db_categories = cat_df['shop_category'].tolist() if not cat_df.empty else []
    category_options = list(dict.fromkeys(default_categories + db_categories))
except:
    category_options = default_categories

if t1 is not None:
    with t1:
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
                rent_price = st.number_input("ثمن الكراء (درهم) *", min_value=0.0, step=100.0)
                if st.form_submit_button("حفظ"):
                    if name and rent_price > 0:
                        c.execute("INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, phone) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (name, cin, address, shop_category, contract, str(start_date), rent_price, phone))
                        st.success("تم حفظ المكتري!")

if t2 is not None:
    with t2:
        st.subheader("تسجيل أداء جديد")
        tenants_df = run_query("SELECT id, name, rent_price, start_date FROM tenants") 
        if not tenants_df.empty:
            t_dict = dict(zip(tenants_df.name, tenants_df.id))
            sel_t = st.selectbox("اختر المكتري", options=list(t_dict.keys()))
            t_id = int(t_dict[sel_t])
            rent = float(tenants_df.loc[tenants_df['name'] == sel_t, 'rent_price'].values[0])
            s_date = str(tenants_df.loc[tenants_df['name'] == sel_t, 'start_date'].values[0])
            
            u_count, u_names, n_names, p_months = get_due_status(s_date, t_id)
            sel_m = st.multiselect("اختر الأشهر:", options=n_names, default=u_names if u_count > 0 else [])
            
            with st.form("payment_form", clear_on_submit=True):
                amt = st.number_input("المبلغ (درهم)", value=float(rent * len(sel_m)), min_value=0.0, step=100.0)
                p_date = st.date_input("تاريخ الأداء", datetime.today())
                if st.form_submit_button("تسجيل الأداء"):
                    if len(sel_m) > 0:
                        c.execute("INSERT INTO payments (tenant_id, tenant_name, months_paid, amount, payment_date, paid_months_names) VALUES (%s, %s, %s, %s, %s, %s)", (t_id, sel_t, len(sel_m), amt, str(p_date), "، ".join(sel_m)))
                        st.success("تم التسجيل!")
                        st.rerun()

if t3 is not None:
    with t3:
        st.subheader("تقرير التوريد للبنك")
        d1, d2 = st.columns(2)
        start_d = d1.date_input("من تاريخ", value=datetime.today().replace(day=1), key="b_d1")
        end_d = d2.date_input("إلى تاريخ", value=datetime.today(), key="b_d2")
        df = run_query("SELECT tenant_name AS \"المكتري\", amount AS \"المبلغ\", payment_date AS \"التاريخ\" FROM payments WHERE payment_date BETWEEN %s AND %s", (str(start_d), str(end_d)))
        if not df.empty:
            st.dataframe(df, width='stretch')
            st.success(f"الإجمالي: {df['المبلغ'].sum()} درهم")

# --- الواجهة 4: المتقاعسون (مع استعادة جميع الميزات) ---
if t4 is not None:
    with t4:
        st.subheader("الإنذارات ومتابعة المراسلات وطلبات الإلغاء")
        defaulter_filter_cat = st.selectbox("فلترة المتقاعسين حسب الصنف:", options=["الكل"] + category_options, key="def_cat_filter")
        
        q = "SELECT id, name, cin, address, shop_category, rent_price, phone, start_date FROM tenants"
        p = ()
        if defaulter_filter_cat != "الكل":
            q += " WHERE shop_category = %s"
            p = (defaulter_filter_cat,)
            
        tenants_df = run_query(q, p)
        
        defaulters = []
        raw_defaulters = []
        for index, row in tenants_df.iterrows():
            t_id = int(row['id'])
            unpaid_count, unpaid_names, _, _ = get_due_status(str(row['start_date']), t_id)
            if unpaid_count > 0:
                defaulters.append({
                    "الاسم": row['name'], "الهاتف": row['phone'],
                    "أشهر التأخير": unpaid_count, "المبلغ المتأخر": unpaid_count * row['rent_price'],
                    "الأشهر المعنية": "، ".join(unpaid_names)
                })
                raw_defaulters.append(row)
                
        if defaulters:
            st.dataframe(pd.DataFrame(defaulters), width='stretch')
            
            # قسم الميزات الذي يظهر فقط للمشرفين
            if role in ["SuperAdmin", "LocalAdmin"]:
                st.markdown("---")
                st.subheader("إجراءات المتقاعسين (واتساب / إنذارات / إفراغ)")
                
                defaulter_names = [d['name'] for d in raw_defaulters]
                selected_def_name = st.selectbox("اختر المكتري لاتخاذ الإجراء:", options=defaulter_names)
                
                if selected_def_name:
                    s_row = next(item for item in raw_defaulters if item['name'] == selected_def_name)
                    sel_id = int(s_row['id'])
                    sel_phone = str(s_row['phone'])
                    u_cnt, u_nms, _, _ = get_due_status(str(s_row['start_date']), sel_id)
                    tot_debt = u_cnt * s_row['rent_price']
                    
                    # 1. الواتساب
                    if sel_phone and sel_phone.lower() != 'nan' and sel_phone.strip() != '':
                        phone_clean = sel_phone.replace(" ", "").replace("+", "")
                        msg = f"السلام عليكم السيد(ة) {selected_def_name}، المرجو تسوية وضعية الكراء الخاصة بالمحل. الشهور المتأخرة: {u_cnt} أشهر بمبلغ {tot_debt} درهم."
                        whatsapp_url = f"https://wa.me/{phone_clean}?text={urllib.parse.quote(msg)}"
                        st.markdown(f"**تواصل معه:** [📱 إرسال رسالة تذكير عبر الواتساب]({whatsapp_url})", unsafe_allow_html=True)
                    else:
                        st.warning("رقم الهاتف غير مسجل لهذا المكتري، لا يمكن إرسال واتساب.")
                        
                    # 2. ملفات الإنذار
                    c.execute("SELECT notice_1_filename, notice_2_filename, cancellation_filename FROM tenants WHERE id = %s", (sel_id,))
                    f_res = c.fetchone()
                    
                    st.markdown("### إدارة ملفات الإنذار والإفراغ")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**الإنذار الأول**")
                        if f_res and f_res[0]: st.success(f"مرفوع: {f_res[0]}")
                        with st.form("form_n1", clear_on_submit=True):
                            f1 = st.file_uploader("رفع الإنذار الأول", type=["pdf", "png", "jpg"], key="n1")
                            if st.form_submit_button("حفظ"):
                                if f1:
                                    fb, fn = get_file_data(f1)
                                    c.execute("UPDATE tenants SET notice_1_file = %s, notice_1_filename = %s WHERE id = %s", (fb, fn, sel_id))
                                    st.success("تم الرفع!")
                                    st.rerun()
                    with col2:
                        st.markdown("**الإنذار الثاني**")
                        if f_res and f_res[1]: st.success(f"مرفوع: {f_res[1]}")
                        with st.form("form_n2", clear_on_submit=True):
                            f2 = st.file_uploader("رفع الإنذار الثاني", type=["pdf", "png", "jpg"], key="n2")
                            if st.form_submit_button("حفظ"):
                                if f2:
                                    fb, fn = get_file_data(f2)
                                    c.execute("UPDATE tenants SET notice_2_file = %s, notice_2_filename = %s WHERE id = %s", (fb, fn, sel_id))
                                    st.success("تم الرفع!")
                                    st.rerun()
                    with col3:
                        st.markdown("**طلب الإفراغ / الإلغاء**")
                        if f_res and f_res[2]: st.success(f"مرفوع: {f_res[2]}")
                        with st.form("form_c", clear_on_submit=True):
                            fc = st.file_uploader("رفع طلب الإفراغ", type=["pdf", "png", "jpg"], key="nc")
                            if st.form_submit_button("حفظ"):
                                if fc:
                                    fb, fn = get_file_data(fc)
                                    c.execute("UPDATE tenants SET cancellation_file = %s, cancellation_filename = %s WHERE id = %s", (fb, fn, sel_id))
                                    st.success("تم الرفع!")
                                    st.rerun()
        else:
            st.success("لا توجد متقاعسين.")

if t5 is not None:
    with t5:
        st.subheader("البحث عن مكتري")
        search_q = st.text_input("أدخل اسم المكتري للبحث:")
        if search_q:
            df_search = run_query("SELECT * FROM tenants WHERE name ILIKE %s", (f"%{search_q}%",))
            if not df_search.empty:
                st.write(f"**الاسم:** {df_search.iloc[0]['name']} | **الهاتف:** {df_search.iloc[0].get('phone', 'غير متوفر')}")

if t6 is not None:
    with t6:
        st.subheader("إلغاء عملية أداء مسجلة بالخطأ")
        df_recent = run_query("SELECT id, tenant_name, amount, payment_date FROM payments ORDER BY id DESC LIMIT 20")
        if not df_recent.empty:
            st.dataframe(df_recent)
            pid = st.number_input("رقم العملية للحذف:", min_value=0, step=1, value=0)
            if st.button("حذف العملية") and pid > 0:
                c.execute("DELETE FROM payments WHERE id = %s", (int(pid),))
                st.success("تم الحذف بنجاح!")
                st.rerun()

if t7 is not None:
    with t7:
        st.subheader("إدارة وتعديل المكترين")
        tenants_edit_df = run_query("SELECT id, name FROM tenants")
        if not tenants_edit_df.empty:
            edit_dict = dict(zip(tenants_edit_df.name, tenants_edit_df.id))
            sel_e = st.selectbox("اختر المكتري للتعديل:", options=list(edit_dict.keys()))
            t_edit_id = int(edit_dict[sel_e])
            c.execute("SELECT phone, address, rent_price FROM tenants WHERE id = %s", (t_edit_id,))
            res_tenant = c.fetchone()
            if res_tenant:
                with st.form("edit_form"):
                    n_ph = st.text_input("الهاتف:", value=res_tenant[0] if res_tenant[0] else "")
                    n_ad = st.text_input("العنوان:", value=res_tenant[1] if res_tenant[1] else "")
                    n_rn = st.number_input("الثمن:", value=float(res_tenant[2]) if res_tenant[2] else 0.0)
                    if st.form_submit_button("حفظ التعديلات"):
                        c.execute("UPDATE tenants SET phone = %s, address = %s, rent_price = %s WHERE id = %s", (n_ph, n_ad, n_rn, t_edit_id))
                        st.success("تم التعديل!")
                        st.rerun()

if t8 is not None:
    with t8:
        st.subheader("النسخ الاحتياطي")
        df_all = run_query("SELECT name, cin, address, rent_price FROM tenants")
        if not df_all.empty:
            st.dataframe(df_all)
