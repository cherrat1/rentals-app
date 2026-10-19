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
            # يمكنك تعديل أسماء المستخدمين وكلمات المرور والصلاحيات هنا بحرية:
            # 1. المشرف العام (له كل الصلاحيات)
            if username == "admin" and password == "admin123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "المشرف العام"
                st.session_state["role"] = "SuperAdmin"
                st.success("مرحباً بك أيها المشرف العام!")
                st.rerun()
            # 2. مشرف الشؤون المالية (مخصص للأداءات وتقارير البنك فقط)
            elif username == "finance" and password == "fin123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "مشرف الشؤون المالية"
                st.session_state["role"] = "FinanceAdmin"
                st.success("مرحباً بك! تم تسجيل الدخول بصلاحيات المالية.")
                st.rerun()
            # 3. المشرف الإداري (مخصص لإدارة المكترين والمتقاعسين فقط)
            elif username == "admin_local" and password == "loc123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "المشرف الإداري"
                st.session_state["role"] = "LocalAdmin"
                st.success("مرحباً بك! تم تسجيل الدخول بصلاحيات الإدارة.")
                st.rerun()
            # 4. مشاهد عادي (للاطلاع فقط)
            elif username == "viewer" and password == "view123":
                st.session_state["authenticated"] = True
                st.session_state["username"] = "مستخدم مشاهد"
                st.session_state["role"] = "Viewer"
                st.success("مرحباً بك! وضع المشاهدة فقط.")
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")
    st.stop()

# شريط جانبي لمعلومات المستخدم وتسجيل الخروج
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

# إنشاء الجداول الأساسية
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

st.title("🏢 نظام تسيير كراء المحلات التجاري")

# تخصيص الألسنة (Tabs) بناءً على صلاحية المشرف
role = st.session_state["role"]

if role == "SuperAdmin":
    # المشرف العام ترى لديه كافة الأقسام
    tab_names = ["➕ إضافة مكتري", "💰 تسجيل أداء", "🏦 تقرير البنك", "⚖️ المتقاعسون", "🔍 البحث", "🗑️ تصحيح الأخطاء", "⚙️ إدارة المكترين", "💾 النسخ الاحتياطي"]
    tabs = st.tabs(tab_names)
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7]

elif role == "FinanceAdmin":
    # مشرف المالية يرى فقط: تسجيل الأداء، تقرير البنك، البحث، النسخ الاحتياطي للأداءات
    tabs = st.tabs(["💰 تسجيل أداء", "🏦 تقرير البنك", "🔍 البحث"])
    t2, t3, t5 = tabs[0], tabs[1], tabs[2]
    t1 = t4 = t6 = t7 = t8 = None

elif role == "LocalAdmin":
    # المشرف الإداري يرى فقط: إضافة مكتري، المتقاعسون، البحث، إدارة المكترين
    tabs = st.tabs(["➕ إضافة مكتري", "⚖️ المتقاعسون", "🔍 البحث", "⚙️ إدارة المكترين"])
    t1, t4, t5, t7 = tabs[0], tabs[1], tabs[2], tabs[3]
    t2 = t3 = t6 = t8 = None

else:
    # المشاهد العادي يرى فقط: البحث وتقرير البنك والمتقاعسون
    tabs = st.tabs(["🔍 البحث", "🏦 تقرير البنك", "⚖️ المتقاعسون"])
    t3, t4, t5 = tabs[1], tabs[2], tabs[0]
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
    cat_df = run_query("SELECT DISTINCT shop_category FROM tenants WHERE shop_category IS NOT NULL AND shop_category != ''")
    db_categories = cat_df['shop_category'].tolist() if not cat_df.empty else []
    category_options = list(dict.fromkeys(default_categories + db_categories))
except:
    category_options = default_categories


# --- الواجهة 1: إضافة مكتري ---
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
                rent_price = st.number_input("ثمن الكراء الشهري (درهم) *", min_value=0.0, step=100.0)
                
                id_card_file = st.file_uploader("نسخة البطاقة الوطنية", type=["pdf", "png", "jpg", "jpeg"], key="add_id_file")
                contract_file = st.file_uploader("نسخة عقد الكراء", type=["pdf", "png", "jpg", "jpeg"], key="add_contract_file")
                conditions_file = st.file_uploader("كناش التحملات", type=["pdf", "png", "jpg", "jpeg"], key="add_cond_file")
                
                if st.form_submit_button("حفظ بيانات المكتري"):
                    if name and rent_price > 0:
                        id_bytes, id_name = get_file_data(id_card_file)
                        contract_bytes, contract_name = get_file_data(contract_file)
                        cond_bytes, cond_name = get_file_data(conditions_file)
                        
                        c.execute(
                            "INSERT INTO tenants (name, cin, address, shop_category, contract_id, start_date, rent_price, phone, "
                            "id_card_file, id_card_filename, contract_file, contract_filename, conditions_file, conditions_filename) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (name, cin, address, shop_category, contract, str(start_date), rent_price, phone, 
                             id_bytes, id_name, contract_bytes, contract_name, cond_bytes, cond_name)
                        )
                        st.success("تم حفظ المكتري بنجاح!")
                    else:
                        st.error("المرجو إدخال الاسم وثمن الكراء.")


# --- الواجهة 2: تسجيل الأداء ---
if t2 is not None:
    with t2:
        st.subheader("تسجيل أداء جديد مع وصل الدفع")
        selected_filter_cat = st.selectbox("فلترة المكترين حسب الصنف:", options=["الكل"] + category_options, key="pay_cat_filter")
        tenants_df = run_query("SELECT id, name, rent_price, start_date FROM tenants") if selected_filter_cat == "الكل" else run_query("SELECT id, name, rent_price, start_date FROM tenants WHERE shop_category = %s", (selected_filter_cat,))
        
        if not tenants_df.empty:
            tenant_dict = dict(zip(tenants_df.name, tenants_df.id))
            selected_tenant = st.selectbox("اختر المكتري", options=list(tenant_dict.keys()))
            t_id = int(tenant_dict[selected_tenant])
            current_tenant_rent = float(tenants_df.loc[tenants_df['name'] == selected_tenant, 'rent_price'].values[0])
            start_date_str = str(tenants_df.loc[tenants_df['name'] == selected_tenant, 'start_date'].values[0])
            
            unpaid_count, unpaid_names, next_months_names, paid_months = get_due_status(start_date_str, t_id)
            selected_months = st.multiselect("اختر الأشهر المراد أداؤها:", options=next_months_names, default=unpaid_names if unpaid_count > 0 else [])
            months_paid = len(selected_months)
            calculated_amount = float(current_tenant_rent * months_paid) if current_tenant_rent else 0.0
            
            with st.form("payment_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                amount = c1.number_input("المبلغ الإجمالي المدفوع (درهم)", value=calculated_amount, min_value=0.0, step=100.0)
                payment_date = c2.date_input("تاريخ الأداء", datetime.today())
                employee_name = st.text_input("اسم الموظف المستخلص")
                receipt_file = st.file_uploader("صورة أو ملف وصل الأداء", type=["pdf", "png", "jpg", "jpeg"], key="payment_receipt_file")
                
                if st.form_submit_button("تأكيد وتسجيل الأداء"):
                    if months_paid == 0:
                        st.warning("المرجو اختيار شهر واحد على الأقل.")
                    else:
                        paid_months_str = "، ".join(selected_months)
                        receipt_bytes, receipt_name = get_file_data(receipt_file)
                        c.execute("INSERT INTO payments (tenant_id, tenant_name, months_paid, amount, payment_date, employee, paid_months_names, receipt_file, receipt_filename) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                  (t_id, selected_tenant, months_paid, amount, str(payment_date), employee_name, paid_months_str, receipt_bytes, receipt_name))
                        st.success("تم تسجيل الأداء بنجاح!")
                        st.rerun()


# --- الواجهة 3: تقرير البنك ---
if t3 is not None:
    with t3:
        st.subheader("تقرير التوريد للبنك")
        d1, d2 = st.columns(2)
        start_d = d1.date_input("من تاريخ", value=datetime.today().replace(day=1), key="b_d1")
        end_d = d2.date_input("إلى تاريخ", value=datetime.today(), key="b_d2")
        df = run_query("SELECT tenant_name AS \"اسم المكتري\", months_paid AS \"عدد الأشهر\", paid_months_names AS \"الأشهر المؤداة\", amount AS \"المبلغ\", payment_date AS \"تاريخ الأداء\", employee AS \"الموظف\" FROM payments WHERE payment_date BETWEEN %s AND %s", (str(start_d), str(end_d)))
        if not df.empty:
            st.dataframe(df, width='stretch')
            st.success(f"المبلغ الإجمالي الموجه للبنك: {df['المبلغ'].sum()} درهم")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='التقرير')
            st.download_button("📥 تحميل التقرير كملف Excel", data=output.getvalue(), file_name="تقرير_البنك.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("لا توجد أداءات في هذه الفترة.")


# --- الواجهة 4: المتقاعسون ---
if t4 is not None:
    with t4:
        st.subheader("الإنذارات ومتابعة المراسلات وطلبات الإلغاء")
        defaulter_filter_cat = st.selectbox("فلترة المتقاعسين حسب الصنف:", options=["الكل"] + category_options, key="def_cat_filter")
        tenants_df = run_query("SELECT DISTINCT id, name, cin, address, shop_category, rent_price, phone, start_date FROM tenants") if defaulter_filter_cat == "الكل" else run_query("SELECT DISTINCT id, name, cin, address, shop_category, rent_price, phone, start_date FROM tenants WHERE shop_category = %s", (defaulter_filter_cat,))
        
        defaulters = []
        for index, row in tenants_df.iterrows():
            t_id = int(row['id'])
            unpaid_count, unpaid_names, _, _ = get_due_status(str(row['start_date']), t_id)
            if unpaid_count > 0:
                defaulters.append({
                    "id": t_id, "الاسم": row['name'], "البطاقة": row['cin'], "العنوان": row['address'],
                    "عدد أشهر التأخير": unpaid_count, "المبلغ المتأخر": unpaid_count * row['rent_price'],
                    "الأشهر المتأخرة": "، ".join(unpaid_names)
                })
        if defaulters:
            st.dataframe(pd.DataFrame(defaulters).drop(columns=["id"]), width='stretch')
        else:
            st.success("لا توجد متقاعسين.")


# --- الواجهة 5: البحث والتصفية ---
if t5 is not None:
    with t5:
        st.subheader("البحث عن مكتري وعرض المرفقات")
        search_q = st.text_input("أدخل اسم المكتري للبحث:")
        if search_q:
            df_search = run_query("SELECT * FROM tenants WHERE name ILIKE %s", (f"%{search_q}%",))
            if not df_search.empty:
                t_data = df_search.iloc[0]
                st.write(f"**الاسم:** {t_data['name']} | **العنوان:** {t_data['address']} | **الهاتف:** {t_data.get('phone', 'غير متوفر')}")
            else:
                st.warning("لم يتم العثور على مكتري بهذا الاسم.")


# --- الواجهة 6: تصحيح الأخطاء ---
if t6 is not None:
    with t6:
        st.subheader("إلغاء عملية أداء مسجلة بالخطأ")
        df_recent = run_query("SELECT id AS \"رقم العملية\", tenant_name AS \"اسم المكتري\", amount AS \"المبلغ\", payment_date AS \"تاريخ الأداء\" FROM payments ORDER BY id DESC LIMIT 30")
        if not df_recent.empty:
            st.dataframe(df_recent, width='stretch')
            pid = st.number_input("أدخل رقم العملية المراد حذفها:", min_value=0, step=1, value=0)
            if st.button("🗑️ حذف العملية"):
                if pid > 0:
                    c.execute("DELETE FROM payments WHERE id = %s", (int(pid),))
                    st.success("تم الحذف بنجاح!")
                    st.rerun()


# --- الواجهة 7: إدارة المكترين ---
if t7 is not None:
    with t7:
        st.subheader("إدارة وتعديل المكترين")
        tenants_edit_df = run_query("SELECT id, name FROM tenants")
        if not tenants_edit_df.empty:
            edit_dict = dict(zip(tenants_edit_df.name, tenants_edit_df.id))
            selected_edit_tenant = st.selectbox("اختر المكتري للتعديل:", options=list(edit_dict.keys()))
            t_edit_id = int(edit_dict[selected_edit_tenant])
            
            c.execute("SELECT phone, shop_category, rent_price, start_date, address FROM tenants WHERE id = %s", (t_edit_id,))
            res_tenant = c.fetchone()
            if res_tenant:
                with st.form("edit_form"):
                    new_address = st.text_input("تحديث العنوان:", value=res_tenant[4] if res_tenant[4] else "")
                    new_phone = st.text_input("تحديث الهاتف:", value=res_tenant[0] if res_tenant[0] else "")
                    new_rent = st.number_input("تحديث ثمن الكراء:", value=float(res_tenant[2]) if res_tenant[2] else 0.0)
                    
                    if st.form_submit_button("حفظ التعديلات"):
                        c.execute("UPDATE tenants SET address = %s, phone = %s, rent_price = %s WHERE id = %s", (new_address, new_phone, new_rent, t_edit_id))
                        st.success("تم التعديل بنجاح!")
                        st.rerun()


# --- الواجهة 8: النسخ الاحتياطي ---
if t8 is not None:
    with t8:
        st.subheader("💾 النسخ الاحتياطي وتصدير البيانات")
        df_all = run_query("SELECT name AS \"الاسم\", cin AS \"البطاقة\", address AS \"العنوان\", rent_price AS \"الثمن\" FROM tenants")
        if not df_all.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_all.to_excel(writer, index=False, sheet_name='المكترون')
            st.download_button("📥 تحميل نسخة المكترين Excel", data=output.getvalue(), file_name="نسخه_المكترين.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
