import streamlit as st
import sqlite3
import os
import base64
import urllib.parse
import calendar as pycal
from datetime import datetime

# ───────────────────────────────
# 1. 接続先の自動判別
# ───────────────────────────────
USE_EXTERNAL_DB = "postgres" in st.secrets

if USE_EXTERNAL_DB:
    import psycopg2
    from psycopg2.extras import DictCursor
    conn_info = "🌐 外部DB(Supabase)に接続中"
else:
    import sqlite3
    conn_info = "🏠 ローカルDB(SQLite)に接続中"

# ───────────────────────────────
# 2. 共通DB操作関数
# ───────────────────────────────
def get_db_connection():
    if USE_EXTERNAL_DB:
        return psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"]
        )
    else:
        return sqlite3.connect('live_reservation.db', check_same_thread=False)

def run_query(query, params=None, commit=False):
    conn = get_db_connection()
    if not USE_EXTERNAL_DB:
        query = query.replace('%s', '?')
    else:
        query = query.replace('?', '%s')
    
    try:
        if USE_EXTERNAL_DB:
            cur = conn.cursor(cursor_factory=DictCursor)
        else:
            cur = conn.cursor()
        cur.execute(query, params or ())
        if commit:
            conn.commit()
            return None
        res = cur.fetchall()
        return [list(row) if not USE_EXTERNAL_DB else dict(row) for row in res]
    except Exception as e:
        st.error(f"DBエラーだぜ: {e}")
        return []
    finally:
        conn.close()

# ───────────────────────────────
# 3. テーブル初期化
# ───────────────────────────────
id_type = "SERIAL PRIMARY KEY" if USE_EXTERNAL_DB else "INTEGER PRIMARY KEY AUTOINCREMENT"
run_query('CREATE TABLE IF NOT EXISTS site_info (key TEXT PRIMARY KEY, value TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS events (id {id_type}, date TEXT, title TEXT, description TEXT, open_time TEXT, start_time TEXT, price TEXT, location TEXT, image_path TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS users (id {id_type}, email TEXT UNIQUE, password TEXT, name TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS reservations (id {id_type}, event_id INTEGER, user_id INTEGER, name TEXT, people INTEGER, email TEXT, status TEXT DEFAULT \'active\')', commit=True)

# ───────────────────────────────
# 4. ヘルパー関数
# ───────────────────────────────
def get_holiday(y, m, d):
    h = {(2026,1,1):"元日",(2026,1,12):"成人の日",(2026,2,11):"建国記念の日",(2026,2,23):"天皇誕生日",
         (2026,3,20):"春分の日",(2026,4,29):"昭和の日",(2026,5,3):"憲法記念日",(2026,5,4):"みどりの日",
         (2026,5,5):"こどもの日",(2026,5,6):"振替休日",(2026,7,20):"海の日",(2026,8,11):"山の日",
         (2026,9,21):"敬老の日",(2026,9,22):"国民の休日",(2026,9,23):"秋分の日",(2026,10,12):"スポーツの日",
         (2026,11,3):"文化の日",(2026,11,23):"勤労感謝の日"}
    return h.get((y, m, d))

def get_info(key, default=""):
    res = run_query("SELECT value FROM site_info WHERE key=?", (key,))
    if res:
        return res[0][0] if isinstance(res[0], list) else res[0]['value']
    return default

def save_info(key, value):
    if USE_EXTERNAL_DB:
        run_query("INSERT INTO site_info (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, str(value)), commit=True)
    else:
        run_query("INSERT OR REPLACE INTO site_info (key, value) VALUES (?, ?)", (key, str(value)), commit=True)

# ───────────────────────────────
# 5. UI設定 & セッション
# ───────────────────────────────
st.set_page_config(page_title="One Once Over", layout="wide")

if 'is_logged_in' not in st.session_state: st.session_state.is_logged_in = False
if 'user_auth' not in st.session_state: st.session_state.user_auth = None
if 'page' not in st.session_state: st.session_state.page = "top"
if 'selected_date' not in st.session_state: st.session_state.selected_date = None
if 'view_month' not in st.session_state: st.session_state.view_month = datetime.now().month
if 'view_year' not in st.session_state: st.session_state.view_year = datetime.now().year

# クエリパラメータ同期
q_year = st.query_params.get("y")
q_month = st.query_params.get("m")
if q_year and q_month:
    st.session_state.view_year = int(q_year)
    st.session_state.view_month = int(q_month)

# --- 🎨 共通CSS (究極のモバイル調整版) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Noto+Sans+JP:wght@900&display=swap');

    /* アプリ全体の余白を削り取る */
    .block-container { padding: 1rem 0.5rem !important; }
    
    .main-title { font-family: 'Anton', sans-serif !important; font-size: clamp(40px, 10vw, 80px) !important; color: #ff6600 !important; text-shadow: 2px 2px 0px #fff !important; text-align: center !important; margin: 0 !important; }
    .sub-title { font-family: 'Noto Sans JP', sans-serif !important; font-size: 14px !important; color: #00ff00 !important; text-align: center !important; margin-bottom: 10px !important; }

    /* カレンダー制御：横幅を強制 */
    .cal-table { width: 100% !important; border-collapse: collapse !important; table-layout: fixed !important; background: #000 !important; }
    .cal-header { background: #333 !important; color: #fff !important; font-size: 11px !important; padding: 4px 0 !important; border: 1px solid #444 !important; }
    .cal-td { border: 1px solid #444 !important; height: clamp(60px, 15vh, 100px) !important; vertical-align: top !important; padding: 2px !important; overflow: hidden; }
    
    .day-num { font-weight: bold !important; font-size: 14px !important; color: #fff !important; }
    .day-holiday, .day-holiday .day-num { color: #ff4b4b !important; }
    .day-sat, .day-sat .day-num { color: #4b4bff !important; }
    
    /* ライブバッジ：はみ出し防止の要 */
    .event-badge { 
        background: #ff6600 !important; color: #fff !important; font-size: 9px !important; 
        padding: 1px 2px !important; border-radius: 2px !important; margin-top: 2px !important; 
        white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
        display: block !important; width: 100% !important;
    }

    /* ナビゲーションバー：1行に絶対収める */
    .nav-container {
        display: flex; justify-content: space-between; align-items: center;
        width: 100%; background: #111; border: 1px solid #00ff00; border-radius: 8px;
        margin-bottom: 8px; height: 45px;
    }
    .nav-btn {
        flex: 1; text-align: center; color: #00ff00 !important; text-decoration: none !important;
        font-weight: bold; font-size: 12px; line-height: 45px;
    }
    .nav-center {
        flex: 1.5; text-align: center; color: #fff; font-family: 'Anton', sans-serif; font-size: 16px;
    }

    /* 不要な隙間を消す */
    hr { margin: 10px 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# ───────────────────────────────
# 6. サイドバー
# ───────────────────────────────
with st.sidebar:
    st.info(conn_info)
    if st.button("🏠 TOPへ戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    if st.button("📅 予定一覧"): st.session_state.page = "list"; st.rerun()
    
    if st.session_state.is_logged_in:
        st.warning("🛠 OWNER MODE")
        if st.button("オーナーログアウト"): st.session_state.is_logged_in = False; st.rerun()
    else:
        with st.expander("🛠 管理者"):
            opw = st.text_input("Pass", type="password")
            if st.button("Login"):
                if opw == "owner123": st.session_state.is_logged_in = True; st.rerun()

# ───────────────────────────────
# 7. メインロジック
# ───────────────────────────────
if st.session_state.page == "top":
    st.markdown('<h1 class="main-title">One Once Over</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">- ライブ予約サイト -</p>', unsafe_allow_html=True)

    top_img_b64 = get_info("top_image_b64", "")
    if top_img_b64:
        st.image(f"data:image/jpeg;base64,{top_img_b64}", use_container_width=True)
    
    # ナビゲーション
    p_year, p_month = (st.session_state.view_year, st.session_state.view_month - 1) if st.session_state.view_month > 1 else (st.session_state.view_year - 1, 12)
    n_year, n_month = (st.session_state.view_year, st.session_state.view_month + 1) if st.session_state.view_month < 12 else (st.session_state.view_year + 1, 1)
    
    nav_html = f"""
    <div class="nav-container">
        <a href="./?y={p_year}&m={p_month}" target="_self" class="nav-btn">◀ PREV</a>
        <div class="nav-center">{st.session_state.view_year} / {st.session_state.view_month:02d}</div>
        <a href="./?y={n_year}&m={n_month}" target="_self" class="nav-btn">NEXT ▶</a>
    </div>
    """
    st.markdown(nav_html, unsafe_allow_html=True)

    # カレンダー
    cal = pycal.Calendar(0)
    month_days = cal.monthdayscalendar(st.session_state.view_year, st.session_state.view_month)
    rows = run_query("SELECT date, title FROM events")
    live_data = { (r[0] if isinstance(r, list) else r['date']): r for r in rows }

    html = '<table class="cal-table"><tr>'
    for d_name in ["月", "火", "水", "木", "金", "土", "日"]: 
        html += f'<th class="cal-header">{d_name}</th>'
    html += '</tr>'
    
    for week in month_days:
        html += '<tr>'
        for idx, day in enumerate(week):
            if day == 0: 
                html += '<td style="border:none; background:transparent;"></td>'
            else:
                d_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day:02d}"
                hol = get_holiday(st.session_state.view_year, st.session_state.view_month, day)
                cls = "day-holiday" if (hol or idx == 6) else "day-sat" if idx == 5 else ""
                html += f'<td class="cal-td {cls}"><a href="./?date={d_str}" target="_self" style="text-decoration:none; color:inherit;">'
                html += f'<span class="day-num">{day}</span>'
                if d_str in live_data:
                    title = live_data[d_str][1] if isinstance(live_data[d_str], list) else live_data[d_str]['title']
                    html += f'<div class="event-badge">{title}</div>'
                html += '</a></td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

    if st.query_params.get("date"):
        st.session_state.selected_date = st.query_params.get("date")
        st.session_state.page = "detail"; st.rerun()

elif st.session_state.page == "detail":
    if st.button("← TOP"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    ev = run_query("SELECT * FROM events WHERE date=?", (st.session_state.selected_date,))
    if ev:
        e = ev[0]
        if isinstance(e, list): e = {"id":e[0], "title":e[2], "description":e[3], "open_time":e[4], "start_time":e[5], "price":e[6], "location":e[7], "image_path":e[8]}
        st.markdown(f'### {e["title"]}')
        if e["image_path"] and os.path.exists(e["image_path"]): st.image(e["image_path"], use_container_width=True)
        st.write(f"📅 {st.session_state.selected_date} / 📍 {e['location']}")
        with st.form("res_form"):
            n = st.text_input("お名前"); p = st.number_input("人数", 1, 10, 1)
            if st.form_submit_button("予約確定"):
                run_query("INSERT INTO reservations (event_id, name, people) VALUES (?,?,?)", (e['id'], n, p), commit=True)
                st.success("予約完了だぜ！")

elif st.session_state.page == "list":
    st.markdown('### SCHEDULE')
    res = run_query("SELECT date, title FROM events ORDER BY date ASC")
    for r in res:
        d, t = (r[0], r[1]) if isinstance(r, list) else (r['date'], r['title'])
        if st.button(f"{d} | {t}", use_container_width=True):
            st.session_state.selected_date = d; st.session_state.page = "detail"; st.rerun()
