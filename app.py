import streamlit as st
import sqlite3
import os
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
        conn = sqlite3.connect('live_reservation.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row # これで名前でデータが引けるようになる
        return conn

def run_query(query, params=None, commit=False):
    conn = get_db_connection()
    if not USE_EXTERNAL_DB:
        query = query.replace('%s', '?')
    else:
        query = query.replace('?', '%s')
    
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        if commit:
            conn.commit()
            return None
        res = cur.fetchall()
        # どの環境でも辞書形式(名前で引ける)に変換
        return [dict(row) for row in res]
    except Exception as e:
        if "column" not in str(e).lower():
            st.error(f"DBエラーだぜ: {e}")
        return []
    finally:
        conn.close()

def img_to_base64(uploaded_file):
    if uploaded_file is not None:
        return base64.b64encode(uploaded_file.read()).decode()
    return None

# ───────────────────────────────
# 3. テーブル初期化 & カラム自動追加
# ───────────────────────────────
id_type = "SERIAL PRIMARY KEY" if USE_EXTERNAL_DB else "INTEGER PRIMARY KEY AUTOINCREMENT"
run_query('CREATE TABLE IF NOT EXISTS site_info (key TEXT PRIMARY KEY, value TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS events (id {id_type}, date TEXT, title TEXT, description TEXT, open_time TEXT, start_time TEXT, performance_time TEXT, price TEXT, location TEXT, image_data TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS reservations (id {id_type}, event_id INTEGER, name TEXT, people INTEGER, email TEXT, status TEXT DEFAULT \'active\')', commit=True)

# 念のためカラム追加（既存DB対策）
for col in ["performance_time", "image_data"]:
    try: run_query(f"ALTER TABLE events ADD COLUMN {col} TEXT", commit=True)
    except: pass

# ───────────────────────────────
# 4. UI・スタイル設定
# ───────────────────────────────
st.set_page_config(page_title="One Once Over", layout="wide")

def get_info(key, default=""):
    res = run_query("SELECT value FROM site_info WHERE key=?", (key,))
    return res[0]['value'] if res else default

bg_img = get_info("bg_image", "")
top_img = get_info("top_image", "")

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Noto+Sans+JP:wght@900&display=swap');
    .stApp {{ background: {f'url(data:image/png;base64,{bg_img})' if bg_img else '#0e1117'}; background-size: cover; background-attachment: fixed; }}
    .block-container {{ padding: 2rem 0.5rem !important; }}
    .main-title-container {{ padding-top: 50px !important; margin-bottom: 10px !important; }}
    .main-title {{ font-family: 'Anton', sans-serif !important; font-size: clamp(40px, 15vw, 90px) !important; color: #ff6600 !important; text-shadow: 3px 3px 0px #fff !important; text-align: center !important; line-height: 1.0; }}
    .sub-title {{ font-family: 'Noto Sans JP', sans-serif !important; font-size: 16px !important; color: #00ff00 !important; text-align: center !important; margin-top: -10px; }}
    .cal-table {{ width: 100% !important; border-collapse: collapse !important; table-layout: fixed !important; background: rgba(0,0,0,0.8) !important; }}
    .cal-header {{ background: #333 !important; color: #fff !important; font-size: 11px !important; padding: 6px 0 !important; border: 1px solid #444 !important; }}
    .cal-td {{ border: 1px solid #444 !important; height: clamp(70px, 15vh, 110px) !important; vertical-align: top !important; padding: 4px !important; }}
    .day-num {{ font-weight: bold !important; font-size: 16px !important; color: #fff !important; }}
    .event-badge {{ background: #ff6600 !important; color: #fff !important; font-size: 10px !important; padding: 2px !important; border-radius: 3px !important; margin-top: 4px !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; display: block !important; width: 100% !important; text-align: center; }}
    .nav-container {{ display: flex; justify-content: space-between; align-items: center; width: 100%; background: rgba(17,17,17,0.9); border: 2px solid #00ff00; border-radius: 10px; margin-bottom: 15px; height: 50px; }}
    .nav-btn {{ flex: 1; text-align: center; color: #00ff00 !important; text-decoration: none !important; font-weight: bold; font-size: 14px; line-height: 50px; }}
    .nav-center {{ flex: 1.5; text-align: center; color: #fff; font-family: 'Anton', sans-serif; font-size: 20px; }}
    </style>
    """, unsafe_allow_html=True)

# ───────────────────────────────
# 5. セッション & サイドバー
# ───────────────────────────────
for k in ['is_logged_in', 'page', 'selected_date', 'view_month', 'view_year']:
    if k not in st.session_state:
        st.session_state[k] = datetime.now().month if k == 'view_month' else datetime.now().year if k == 'view_year' else "top" if k == 'page' else False

with st.sidebar:
    st.info(conn_info)
    if st.button("🏠 TOPへ戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    if st.button("📅 予定一覧"): st.session_state.page = "list"; st.rerun()
    if st.session_state.is_logged_in:
        st.warning("🛠 OWNER MODE")
        if st.button("ライブ予定の管理/登録"): st.session_state.page = "admin_events"; st.rerun()
        if st.button("サイト外観・画像設定"): st.session_state.page = "admin_style"; st.rerun()
        if st.button("オーナーログアウト"): st.session_state.is_logged_in = False; st.rerun()
    else:
        with st.expander("🛠 管理者"):
            opw = st.text_input("Pass", type="password")
            if st.button("Login"):
                if opw == "owner123": st.session_state.is_logged_in = True; st.rerun()

# ───────────────────────────────
# 6. メインロジック
# ───────────────────────────────

# --- TOPページ ---
if st.session_state.page == "top":
    st.markdown('<div class="main-title-container"><h1 class="main-title">One Once Over</h1></div>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">- ライブ予約サイト -</p>', unsafe_allow_html=True)
    if top_img: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{top_img}" style="max-width:100%; border-radius:15px; margin-bottom:20px; border:2px solid #ff6600;"></div>', unsafe_allow_html=True)
    
    # ナビ
    q_y, q_m = st.query_params.get("y"), st.query_params.get("m")
    if q_y and q_m: st.session_state.view_year, st.session_state.view_month = int(q_y), int(q_m)
    p_y, p_m = (st.session_state.view_year, st.session_state.view_month - 1) if st.session_state.view_month > 1 else (st.session_state.view_year - 1, 12)
    n_y, n_m = (st.session_state.view_year, st.session_state.view_month + 1) if st.session_state.view_month < 12 else (st.session_state.view_year + 1, 1)
    
    st.markdown(f'<div class="nav-container"><a href="./?y={p_y}&m={p_m}" target="_self" class="nav-btn">◀ PREV</a><div class="nav-center">{st.session_state.view_year} / {st.session_state.view_month:02d}</div><a href="./?y={n_y}&m={n_m}" target="_self" class="nav-btn">NEXT ▶</a></div>', unsafe_allow_html=True)

    cal = pycal.Calendar(0)
    month_days = cal.monthdayscalendar(st.session_state.view_year, st.session_state.view_month)
    rows = run_query("SELECT date, title FROM events")
    live_map = { r['date']: r['title'] for r in rows }
    
    html = '<table class="cal-table"><tr>' + "".join([f'<th class="cal-header">{d}</th>' for d in ["月","火","水","木","金","土","日"]]) + '</tr>'
    for week in month_days:
        html += '<tr>'
        for idx, day in enumerate(week):
            if day == 0: html += '<td style="border:none; background:transparent;"></td>'
            else:
                d_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day:02d}"
                cls = "day-holiday" if idx == 6 else "day-sat" if idx == 5 else ""
                html += f'<td class="cal-td {cls}"><a href="./?date={d_str}" target="_self" style="text-decoration:none; color:inherit;"><span class="day-num">{day}</span>'
                if d_str in live_map: html += f'<div class="event-badge">{live_map[d_str]}</div>'
                html += '</a></td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)
    if st.query_params.get("date"):
        st.session_state.selected_date = st.query_params.get("date")
        st.session_state.page = "detail"; st.rerun()

# --- 詳細ページ ---
elif st.session_state.page == "detail":
    if st.button("← 戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    # 確実に名前で取得
    ev = run_query("SELECT id, title, open_time, start_time, performance_time, price, location, image_data FROM events WHERE date=?", (st.session_state.selected_date,))
    if ev:
        e = ev[0]
        if e["image_data"]: st.image(f"data:image/png;base64,{e['image_data']}", use_container_width=True)
        st.markdown(f'# {e["title"]}')
        col1, col2 = st.columns(2)
        with col1: st.info(f"📍 場所: {e['location']}\n\n💰 料金: {e['price']}")
        with col2: st.success(f"⏰ Open: {e['open_time']}\n\n🎸 Start: {e['start_time']}\n\n🔥 出演: {e['performance_time']}")
        
        with st.form("res_form"):
            u_name = st.text_input("お名前")
            u_email = st.text_input("メールアドレス")
            u_num = st.number_input("人数", 1, 10, 1)
            if st.form_submit_button("予約する"):
                run_query("INSERT INTO reservations (event_id, name, people, email) VALUES (?,?,?,?)", (e['id'], u_name, u_num, u_email), commit=True)
                st.success("予約完了だぜ！当日待ってるぞ！")

# --- オーナー：イベント管理（再編集機能付き） ---
elif st.session_state.page == "admin_events":
    st.markdown("### 🛠 ライブ予定管理")
    
    # 新規登録
    with st.expander("🆕 新規イベントを登録する"):
        with st.form("new_event"):
            d = st.date_input("日付").strftime('%Y-%m-%d'); t = st.text_input("タイトル")
            ot = st.text_input("開場"); st_t = st.text_input("開演"); pf_t = st.text_input("出演時間")
            loc = st.text_input("場所"); pr = st.text_input("料金")
            img_file = st.file_uploader("ライブ画像", type=['png', 'jpg'])
            if st.form_submit_button("登録"):
                b64 = img_to_base64(img_file)
                run_query("INSERT INTO events (date, title, open_time, start_time, performance_time, location, price, image_data) VALUES (?,?,?,?,?,?,?,?)", (d,t,ot,st_t,pf_t,loc,pr,b64), commit=True)
                st.success("登録したぜ！"); st.rerun()

    st.markdown("---")
    # 既存イベントの編集・削除
    evs = run_query("SELECT * FROM events ORDER BY date DESC")
    for ev in evs:
        with st.expander(f"📝 {ev['date']} | {ev['title']}"):
            with st.form(f"edit_form_{ev['id']}"):
                # 既存の値を初期値としてセット
                u_date = st.text_input("日付 (YYYY-MM-DD)", value=ev['date'])
                u_title = st.text_input("タイトル", value=ev['title'])
                u_ot = st.text_input("開場", value=ev['open_time'])
                u_st = st.text_input("開演", value=ev['start_time'])
                u_pf = st.text_input("出演時間", value=ev['performance_time'])
                u_loc = st.text_input("場所", value=ev['location'])
                u_pr = st.text_input("料金", value=ev['price'])
                
                c1, c2 = st.columns(2)
                if c1.form_submit_button("✅ 変更を保存"):
                    run_query("UPDATE events SET date=?, title=?, open_time=?, start_time=?, performance_time=?, location=?, price=? WHERE id=?", 
                              (u_date, u_title, u_ot, u_st, u_pf, u_loc, u_pr, ev['id']), commit=True)
                    st.success("更新完了！"); st.rerun()
                
                if c2.form_submit_button("🚨 削除"):
                    run_query("DELETE FROM events WHERE id=?", (ev['id'],), commit=True)
                    st.error("削除したぜ！"); st.rerun()

# --- オーナー：スタイル設定 ---
elif st.session_state.page == "admin_style":
    st.subheader("🎨 サイトデザイン設定")
    with st.form("style_form"):
        bg_f = st.file_uploader("背景画像", type=['png', 'jpg'])
        tp_f = st.file_uploader("TOPメイン画像", type=['png', 'jpg'])
        if st.form_submit_button("保存"):
            if bg_f: run_query("INSERT INTO site_info (key, value) VALUES ('bg_image', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (img_to_base64(bg_f),), commit=True)
            if tp_f: run_query("INSERT INTO site_info (key, value) VALUES ('top_image', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (img_to_base64(tp_f),), commit=True)
            st.rerun()
    if st.button("背景リセット"): run_query("DELETE FROM site_info WHERE key='bg_image'", commit=True); st.rerun()

# --- 予定一覧 ---
elif st.session_state.page == "list":
    st.markdown('### SCHEDULE LIST')
    res = run_query("SELECT date, title FROM events ORDER BY date ASC")
    for r in res:
        if st.button(f"{r['date']} | {r['title']}", use_container_width=True):
            st.session_state.selected_date = r['date']; st.session_state.page = "detail"; st.rerun()
