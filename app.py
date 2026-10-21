import streamlit as st
import psycopg2
import urllib.parse
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io

# محاولة استدعاء مكتبة الوورد
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

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

# تخصيص الألسنة بناءً على الصلاحية
role = st.session_state["role"]

if role == "SuperAdmin":
    tab_names = ["➕ إضافة مكتري", "💰 تسجيل أداء", "🏦 تقرير البنك", "⚖️ المتقاعسون", "🔍 البحث والتصفية", "🗑️ تصحيح الأخطاء", "⚙️ إدارة المكترين", "💾 النسخ الاحتياطي"]
    tabs = st.tabs(tab_names)
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7]
elif role == "FinanceAdmin":
    tabs = st.tabs(["💰 تسجيل أداء", "🏦 تقرير البنك", "🔍 البحث والتصفية"])
    t2, t3, t5 = tabs[0], tabs[1], tabs[2]
    t1 = t4 = t6 = t7 = t8 = None
elif role == "LocalAdmin":
    tabs = st.tabs(["➕ إضافة مكتري", "⚖️ المتقاعسون", "🔍 البحث والتصفية", "⚙️ إدارة المكترين"])
    t1, t4, t5, t7 = tabs[0], tabs[1], tabs[2], tabs[3]
    t2 = t3 = t6 = t8 = None
else:
    tabs = st.tabs(["🔍 البحث والتصفية", "🏦 تقرير البنك", "⚖️ المتقاعسون"])
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
        with col2:
            st.markdown("**استيراد المكترين من ملف Excel 📥**")
            excel_default_category = st.selectbox("اختر الصنف الذي ينتمي له هؤلاء المكترون:", options=category_options, key="excel_cat")
            uploaded_file = st.file_uploader("اختر ملف Excel (.xlsx)", type=["xlsx"])
            if uploaded_file is not None:
                df_excel = pd.read_excel(uploaded_file)
                if st.button("تأكيد استيراد البيانات"):
                    imported_count = 0
                    for index, row in df_excel.iterrows():
                        t_name = ""
                        for col in df_excel.columns:
                            if "الاسم" in str(col) or "اسم" in str(col):
                                t_name = str(row[col])
                                break
                        if t_name.strip() != "" and t_name.strip() != "nan":
                            c.execute("INSERT INTO tenants (name, shop_category, start_date, rent_price) VALUES (%s, %s, %s, %s)",
                                      (t_name, excel_default_category, str(datetime.today().date()), 0.0))
                            imported_count += 1
                    st.success(f"تم بنجاح استيراد {imported_count} مكتري!")

# --- الواجهة 2: تسجيل الأداء ---
if t2 is not None:
    with t2:
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
            
            unpaid_count, unpaid_names, next_months_names, paid_months = get_due_status(start_date_str, t_id)
            selected_months = st.multiselect("اختر الأشهر المراد أداؤها:", options=next_months_names, default=unpaid_names if unpaid_count > 0 else [])
            months_paid = len(selected_months)
            
            with st.form("payment_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                payment_date = c1.date_input("تاريخ الأداء", datetime.today())
                employee_name = c2.text_input("اسم الموظف المستخلص")
                
                st.markdown("---")
                # إضافة خيار لاختيار طريقة رفع الوصولات
                receipt_option = st.radio("كيف تريد إرفاق الوصولات؟", 
                                          options=["📄 وصل واحد يجمع كل الأشهر المحددة", "📑 وصل منفصل لكل شهر على حدة"], 
                                          horizontal=True)
                
                single_receipt_file = None
                receipt_files = {}
                
                if months_paid > 0:
                    if receipt_option == "📄 وصل واحد يجمع كل الأشهر المحددة":
                        calculated_amount = float(current_tenant_rent * months_paid)
                        st.info(f"**المبلغ الإجمالي:** {calculated_amount} درهم")
                        single_receipt_file = st.file_uploader("إرفاق الوصل الإجمالي", type=["pdf", "png", "jpg", "jpeg"])
                    else:
                        for m in selected_months:
                            receipt_files[m] = st.file_uploader(f"وصل أداء خاص بشهر: {m} ({current_tenant_rent} درهم)", type=["pdf", "png", "jpg", "jpeg"], key=f"rec_{m}")
                
                if st.form_submit_button("تأكيد وتسجيل الأداء"):
                    if months_paid == 0:
                        st.warning("المرجو اختيار شهر واحد على الأقل.")
                    else:
                        if receipt_option == "📄 وصل واحد يجمع كل الأشهر المحددة":
                            # تسجيل كعملية واحدة مجمعة
                            r_bytes, r_name = get_file_data(single_receipt_file)
                            paid_months_str = "، ".join(selected_months)
                            calculated_amount = float(current_tenant_rent * months_paid)
                            
                            c.execute("INSERT INTO payments (tenant_id, tenant_name, months_paid, amount, payment_date, employee, paid_months_names, receipt_file, receipt_filename) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                      (t_id, selected_tenant, months_paid, calculated_amount, str(payment_date), employee_name, paid_months_str, r_bytes, r_name))
                            
                            st.success(f"✅ تم تسجيل أداء إجمالي بقيمة {calculated_amount} درهم عن {months_paid} أشهر بنجاح!")
                        
                        else:
                            # تسجيل كعمليات منفصلة
                            for m in selected_months:
                                r_file = receipt_files[m]
                                r_bytes, r_name = get_file_data(r_file)
                                
                                c.execute("INSERT INTO payments (tenant_id, tenant_name, months_paid, amount, payment_date, employee, paid_months_names, receipt_file, receipt_filename) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                          (t_id, selected_tenant, 1, current_tenant_rent, str(payment_date), employee_name, m, r_bytes, r_name))
                                
                            st.success(f"✅ تم تسجيل {months_paid} عمليات أداء منفصلة بنجاح، وتم ربط كل شهر بوصله الخاص!")
                        
                        st.rerun()
        else:
            st.warning("لا يوجد مكترين مسجلين.")

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
            
            if role in ["SuperAdmin", "LocalAdmin"]:
                st.markdown("---")
                st.subheader("إجراءات المتقاعسين (واتساب / توليد الإنذارات / الإفراغ)")
                
                defaulter_names = [d['name'] for d in raw_defaulters]
                selected_def_name = st.selectbox("اختر المكتري لاتخاذ الإجراء:", options=defaulter_names)
                
                if selected_def_name:
                    s_row = next(item for item in raw_defaulters if item['name'] == selected_def_name)
                    sel_id = int(s_row['id'])
                    sel_phone = str(s_row['phone'])
                    u_cnt, u_nms, _, _ = get_due_status(str(s_row['start_date']), sel_id)
                    tot_debt = u_cnt * s_row['rent_price']
                    months_str = "، ".join(u_nms)
                    date_today = datetime.today().strftime("%Y-%m-%d")
                    
                    # 1. الواتساب الذكي
                    if sel_phone and sel_phone.lower() != 'nan' and sel_phone.strip() != '':
                        p_clean = sel_phone.replace(" ", "").replace("+", "").replace("-", "")
                        if p_clean.startswith("00212"): p_clean = p_clean[2:]
                        elif p_clean.startswith("0"): p_clean = "212" + p_clean[1:]
                        elif not p_clean.startswith("212"): p_clean = "212" + p_clean
                        msg = f"السلام عليكم السيد(ة) {selected_def_name}، المرجو تسوية وضعية الكراء الخاصة بالمحل. الشهور المتأخرة: {u_cnt} أشهر بمبلغ {tot_debt} درهم."
                        whatsapp_url = f"https://wa.me/{p_clean}?text={urllib.parse.quote(msg)}"
                        st.markdown(f"**تواصل معه مباشرة:** [📱 إرسال رسالة تذكير عبر الواتساب]({whatsapp_url})", unsafe_allow_html=True)
                    else:
                        st.warning("رقم الهاتف غير مسجل لهذا المكتري.")
                    
                    # 2. توليد الوورد
                    def create_word_notice(notice_type):
                        if not HAS_DOCX:
                            return None
                        doc = Document()
                        
                        p_head = doc.add_paragraph()
                        p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        p_head.add_run("المملكة المغربية\nالمجلس الجماعي\nمصلحة الممتلكات\n").bold = True
                        
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
                        else:
                            st.error("⚠️ المرجو تثبيت مكتبة python-docx عبر الشاشة السوداء")
                    with col_gen2:
                        if word_n2:
                            st.download_button("📥 تحميل الإنذار الثاني (Word)", data=word_n2, file_name=f"إنذار_ثاني_{selected_def_name}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

                    # 3. الأرشفة
                    c.execute("SELECT notice_1_filename, notice_2_filename, cancellation_filename FROM tenants WHERE id = %s", (sel_id,))
                    f_res = c.fetchone()
                    
                    st.markdown("### 📁 أرشفة ملفات الإنذارات (بعد التوقيع)")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("**الإنذار الأول**")
                        if f_res and f_res[0]: st.success(f"مرفوع: {f_res[0]}")
                        with st.form("form_n1", clear_on_submit=True):
                            f1 = st.file_uploader("", type=["pdf", "png", "jpg"], key="n1")
                            if st.form_submit_button("حفظ") and f1:
                                fb, fn = get_file_data(f1)
                                c.execute("UPDATE tenants SET notice_1_file = %s, notice_1_filename = %s WHERE id = %s", (fb, fn, sel_id))
                                st.success("تم الرفع!"); st.rerun()
                    with col2:
                        st.markdown("**الإنذار الثاني**")
                        if f_res and f_res[1]: st.success(f"مرفوع: {f_res[1]}")
                        with st.form("form_n2", clear_on_submit=True):
                            f2 = st.file_uploader("", type=["pdf", "png", "jpg"], key="n2")
                            if st.form_submit_button("حفظ") and f2:
                                fb, fn = get_file_data(f2)
                                c.execute("UPDATE tenants SET notice_2_file = %s, notice_2_filename = %s WHERE id = %s", (fb, fn, sel_id))
                                st.success("تم الرفع!"); st.rerun()
                    with col3:
                        st.markdown("**طلب الإفراغ**")
                        if f_res and f_res[2]: st.success(f"مرفوع: {f_res[2]}")
                        with st.form("form_c", clear_on_submit=True):
                            fc = st.file_uploader("", type=["pdf", "png", "jpg"], key="nc")
                            if st.form_submit_button("حفظ") and fc:
                                fb, fn = get_file_data(fc)
                                c.execute("UPDATE tenants SET cancellation_file = %s, cancellation_filename = %s WHERE id = %s", (fb, fn, sel_id))
                                st.success("تم الرفع!"); st.rerun()
        else:
            st.success("لا توجد متقاعسين.")
            
# --- الواجهة 5: البحث والتصفية (النسخة الجديدة الشاملة) ---
if t5 is not None:
    with t5:
        st.subheader("البحث عن مكتري وعرض التفاصيل، الديون، والمرفقات")
        
        all_tenants_df = run_query("SELECT id, name, cin FROM tenants")
        
        if not all_tenants_df.empty:
            options = [""] + [f"{row['name']} - (بطاقة: {row['cin'] if row['cin'] else 'غير متوفر'}) - [ID: {row['id']}]" for _, row in all_tenants_df.iterrows()]
            
            selected_option = st.selectbox("🔍 ابدأ بكتابة اسم المكتري (ستظهر النتائج فوراً دون ضغط أي زر):", options=options)
            
            if selected_option:
                t_id = int(selected_option.split("[ID: ")[1].replace("]", ""))
                df_search = run_query("SELECT * FROM tenants WHERE id = %s", (t_id,))
                
                if not df_search.empty:
                    row = df_search.iloc[0]
                    
                    st.success("✅ تم جلب بيانات المكتري بنجاح:")
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
                            st.write(f"**ثمن الكراء الشهري:** {row.get('rent_price', 0)} درهم")
                            st.write(f"**رقم العقد:** {row.get('contract_id', 'غير متوفر')}")
                    
                    st.markdown("### 💰 الوضعية المالية (الأداءات والديون)")
                    u_cnt, u_nms, _, p_months = get_due_status(str(row['start_date']), t_id)
                    
                    c_stat1, c_stat2 = st.columns(2)
                    with c_stat1:
                        st.info(f"**إجمالي الأشهر المؤداة:** {p_months} أشهر")
                        payments_df = run_query("SELECT amount, payment_date, paid_months_names, receipt_filename, receipt_file FROM payments WHERE tenant_id = %s ORDER BY id DESC", (t_id,))
                        if not payments_df.empty:
                            st.write("**تاريخ الأداءات ووصولات الدفع:**")
                            for p_idx, p_row in payments_df.iterrows():
                                with st.expander(f"📅 دفعة بتاريخ {p_row['payment_date']} | مبلغ {p_row['amount']} درهم"):
                                    st.write(f"**الأشهر التي تم أداؤها:** {p_row['paid_months_names']}")
                                    if pd.notna(p_row.get('receipt_file')) and p_row.get('receipt_file'):
                                        # التصحيح: تحويل الملف إلى صيغة bytes
                                        file_bytes = bytes(p_row['receipt_file'])
                                        st.download_button(label=f"📥 تحميل وصل الأداء ({p_row.get('receipt_filename', 'وصل.pdf')})", data=file_bytes, file_name=p_row.get('receipt_filename', 'وصل.pdf'), key=f"rec_{t_id}_{p_idx}")
                                    else:
                                        st.warning("لا يوجد وصل مرفق لهذه العملية.")
                        else:
                            st.write("لم يتم تسجيل أي أداءات حتى الآن.")

                    with c_stat2:
                        if u_cnt > 0:
                            st.error(f"**إجمالي الأشهر المتأخرة (غير المؤداة):** {u_cnt} أشهر")
                            st.write(f"**الديون المتراكمة:** {u_cnt * row['rent_price']} درهم")
                            st.write(f"**تفصيل الأشهر غير المؤداة:** {'، '.join(u_nms)}")
                        else:
                            st.success("✅ المكتري في وضعية سليمة، لا توجد ديون متأخرة!")

                    st.markdown("### 📁 الوثائق والمرفقات الأساسية")
                    attachments = []
                    # التصحيح: تحويل كافة المرفقات إلى صيغة bytes
                    if pd.notna(row.get('id_card_file')) and row.get('id_card_file'):
                        attachments.append((row.get('id_card_filename', 'البطاقة.pdf'), bytes(row['id_card_file'])))
                    if pd.notna(row.get('contract_file')) and row.get('contract_file'):
                        attachments.append((row.get('contract_filename', 'العقد.pdf'), bytes(row['contract_file'])))
                    if pd.notna(row.get('conditions_file')) and row.get('conditions_file'):
                        attachments.append((row.get('conditions_filename', 'الكناش.pdf'), bytes(row['conditions_file'])))
                    if pd.notna(row.get('notice_1_file')) and row.get('notice_1_file'):
                        attachments.append((row.get('notice_1_filename', 'الإنذار_الأول.pdf'), bytes(row['notice_1_file'])))
                    if pd.notna(row.get('notice_2_file')) and row.get('notice_2_file'):
                        attachments.append((row.get('notice_2_filename', 'الإنذار_الثاني.pdf'), bytes(row['notice_2_file'])))
                    if pd.notna(row.get('cancellation_file')) and row.get('cancellation_file'):
                        attachments.append((row.get('cancellation_filename', 'طلب_الإفراغ.pdf'), bytes(row['cancellation_file'])))
                        
                    if attachments:
                        cols = st.columns(len(attachments))
                        for i, (fname, fbytes) in enumerate(attachments):
                            with cols[i]:
                                st.download_button(label=f"📥 {fname}", data=fbytes, file_name=fname, key=f"dl_main_{t_id}_{i}")
                    else:
                        st.info("لا توجد وثائق أساسية مسجلة لهذا المكتري.")
        else:
            st.info("لا يوجد أي مكتري مسجل في النظام بعد.")
            
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
