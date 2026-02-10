import streamlit as st
import sqlite3
import os
import base64
import calendar as pycal
from datetime import datetime
import urllib.parse

# ───────────────────────────────
# 1. 接続先の自動判別 & 変数定義
# ───────────────────────────────
USE_EXTERNAL_DB = "postgres" in st.secrets

if USE_EXTERNAL_DB:
    import psycopg2
    conn_info = "🌐 外部DB(Supabase)に接続中"
else:
    conn_info = "🏠 ローカルDB(SQLite)に接続中"

# ───────────────────────────────
# 2. 共通DB操作関数（高速化対応版）
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
        conn.row_factory = sqlite3.Row
        return conn

# 🚀 読み込みを速くするためのキャッシュ（10分間保持）
@st.cache_data(ttl=600)
def run_query_cached(query, params=None):
    return run_query(query, params)

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
            st.cache_data.clear() # 更新があったらキャッシュを飛ばす
            return None
        res = cur.fetchall()
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
# 3. テーブル初期化
# ───────────────────────────────
id_type = "SERIAL PRIMARY KEY" if USE_EXTERNAL_DB else "INTEGER PRIMARY KEY AUTOINCREMENT"
run_query('CREATE TABLE IF NOT EXISTS site_info (key TEXT PRIMARY KEY, value TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS events (id {id_type}, date TEXT, title TEXT, description TEXT, open_time TEXT, start_time TEXT, performance_time TEXT, price TEXT, location TEXT, image_data TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS reservations (id {id_type}, event_id INTEGER, name TEXT, people INTEGER, email TEXT, status TEXT DEFAULT \'active\')', commit=True)

# ───────────────────────────────
# 4. UI・スタイル設定
# ───────────────────────────────
st.set_page_config(page_title="One Once Over", layout="wide")

def get_info(key, default=""):
    res = run_query_cached("SELECT value FROM site_info WHERE key=?", (key,))
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
    .cal-table {{ width: 100% !important; border-collapse: collapse !important; table-layout: fixed !important; background: rgba(0,0,0,0.85) !important; }}
    .cal-header {{ background: #333 !important; color: #fff !important; font-size: 11px !important; padding: 6px 0 !important; border: 1px solid #444 !important; }}
    .cal-td {{ border: 1px solid #444 !important; height: clamp(90px, 20vh, 140px) !important; vertical-align: top !important; padding: 4px !important; position: relative; }}
    .day-num {{ font-weight: bold !important; font-size: 16px !important; color: #fff !important; }}
    .cal-img {{ width: 100%; height: 50px; object-fit: cover; border-radius: 4px; margin-top: 2px; border: 1px solid #555; }}
    .event-badge {{ background: #ff6600 !important; color: #fff !important; font-size: 10px !important; padding: 2px !important; border-radius: 3px !important; margin-top: 2px !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; display: block !important; width: 100% !important; text-align: center; }}
    .detail-card {{ background: rgba(0, 0, 0, 0.8) !important; padding: 25px !important; border-radius: 15px !important; color: white !important; margin-bottom: 20px; }}
    .info-box {{ background: rgba(50, 50, 50, 0.9) !important; border-left: 5px solid #ff6600 !important; padding: 15px !important; border-radius: 5px; color: white !important; }}
    .success-box {{ background: rgba(20, 40, 20, 0.9) !important; border-left: 5px solid #00ff00 !important; padding: 15px !important; border-radius: 5px; color: white !important; }}
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
    st.info(conn_info) # ✅ エラー修正済み
    if st.button("🏠 TOPへ戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    if st.button("📅 予定一覧"): st.session_state.page = "list"; st.rerun()
    if st.session_state.is_logged_in:
        st.warning("🛠 OWNER MODE")
        if st.button("🎸 ライブ予定の管理"): st.session_state.page = "admin_events"; st.rerun()
        if st.button("👥 顧客名簿・予約集計"): st.session_state.page = "admin_customers"; st.rerun()
        if st.button("🎨 サイト外観設定"): st.session_state.page = "admin_style"; st.rerun()
        if st.button("Logout"): st.session_state.is_logged_in = False; st.rerun()
    else:
        with st.expander("🛠 管理者"):
            opw = st.text_input("Pass", type="password")
            if st.button("Login"):
                if opw == "owner123": st.session_state.is_logged_in = True; st.rerun()

# ───────────────────────────────
# 6. メインロジック
# ───────────────────────────────

if st.session_state.page == "top":
    st.markdown('<div class="main-title-container"><h1 class="main-title">One Once Over</h1></div>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">- ライブ予約サイト -</p>', unsafe_allow_html=True)
    if top_img: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{top_img}" style="max-width:100%; border-radius:15px; margin-bottom:20px; border:2px solid #ff6600;"></div>', unsafe_allow_html=True)
    
    q_y, q_m = st.query_params.get("y"), st.query_params.get("m")
    if q_y and q_m: st.session_state.view_year, st.session_state.view_month = int(q_y), int(q_m)
    p_y, p_m = (st.session_state.view_year, st.session_state.view_month - 1) if st.session_state.view_month > 1 else (st.session_state.view_year - 1, 12)
    n_y, n_m = (st.session_state.view_year, st.session_state.view_month + 1) if st.session_state.view_month < 12 else (st.session_state.view_year + 1, 1)
    st.markdown(f'<div class="nav-container"><a href="./?y={p_y}&m={p_m}" target="_self" class="nav-btn">◀ PREV</a><div class="nav-center">{st.session_state.view_year} / {st.session_state.view_month:02d}</div><a href="./?y={n_y}&m={n_m}" target="_self" class="nav-btn">NEXT ▶</a></div>', unsafe_allow_html=True)

    cal = pycal.Calendar(0)
    month_days = cal.monthdayscalendar(st.session_state.view_year, st.session_state.view_month)
    rows = run_query_cached("SELECT date, title, image_data FROM events")
    live_map = { r['date']: r for r in rows }
    
    html = '<table class="cal-table"><tr>' + "".join([f'<th class="cal-header">{d}</th>' for d in ["月","火","水","木","金","土","日"]]) + '</tr>'
    for week in month_days:
        html += '<tr>'
        for idx, day in enumerate(week):
            if day == 0: html += '<td style="border:none; background:transparent;"></td>'
            else:
                d_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day:02d}"
                html += f'<td class="cal-td"><a href="./?date={d_str}" target="_self" style="text-decoration:none; color:inherit;"><span class="day-num">{day}</span>'
                if d_str in live_map:
                    ev = live_map[d_str]
                    if ev['image_data']: html += f'<img src="data:image/png;base64,{ev["image_data"]}" class="cal-img">'
                    html += f'<div class="event-badge">{ev["title"]}</div>'
                html += '</a></td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)
    if st.query_params.get("date"):
        st.session_state.selected_date = st.query_params.get("date")
        st.session_state.page = "detail"; st.rerun()

elif st.session_state.page == "detail":
    if st.button("← 戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    ev = run_query_cached("SELECT id, title, open_time, start_time, performance_time, price, location, image_data FROM events WHERE date=?", (st.session_state.selected_date,))
    if ev:
        e = ev[0]
        st.markdown(f'<div class="detail-card">', unsafe_allow_html=True)
        if e["image_data"]: st.image(f"data:image/png;base64,{e['image_data']}", use_container_width=True)
        st.markdown(f'<h1 style="color:#ff6600; font-size:40px; margin-top:10px;">{e["title"]}</h1>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(e['location'])}"
            st.markdown(f"""<div class="info-box">📍 <b>場所:</b> {e['location']}<br><a href="{maps_url}" target="_blank" style="color:#ff6600; text-decoration:none; font-weight:bold;">🗺 Google MAPを表示</a><br>💰 <b>料金:</b> {e['price']}</div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class="success-box">⏰ <b>Open:</b> {e['open_time']}<br>🎸 <b>Start:</b> {e['start_time']}<br>🔥 <b>出演:</b> {e['performance_time']}</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        with st.expander("🎫 予約フォーム", expanded=True):
            with st.form("res_form"):
                u_name = st.text_input("お名前")
                u_email = st.text_input("メールアドレス")
                u_num = st.number_input("人数", 1, 10, 1)
                if st.form_submit_button("予約を確定する"):
                    run_query("INSERT INTO reservations (event_id, name, people, email) VALUES (?,?,?,?)", (e['id'], u_name, u_num, u_email), commit=True)
                    st.balloons(); st.success("予約完了だぜ！")

        # 🚀 オーナー専用：このイベントの予約者リスト
        if st.session_state.is_logged_in:
            st.divider()
            st.subheader("🛠【管理者限定】予約者リスト")
            reserves = run_query("SELECT * FROM reservations WHERE event_id=?", (e['id'],))
            if not reserves:
                st.info("予約者はまだいないぜ。")
            else:
                for r in reserves:
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"👤 {r['name']} 様 ({r['people']}名) | {r['email']}")
                    if c2.button("キャンセル", key=f"del_{r['id']}"):
                        run_query("DELETE FROM reservations WHERE id=?", (r['id'],), commit=True)
                        st.rerun()

elif st.session_state.page == "admin_events":
    st.markdown("### 🛠 ライブ予定管理")
    with st.expander("🆕 新規登録"):
        with st.form("new_event"):
            d = st.date_input("日付").strftime('%Y-%m-%d'); t = st.text_input("タイトル")
            ot = st.text_input("開場"); st_t = st.text_input("開演"); pf_t = st.text_input("出演時間")
            loc = st.text_input("場所"); pr = st.text_input("料金")
            img_file = st.file_uploader("画像", type=['png', 'jpg'])
            if st.form_submit_button("登録"):
                run_query("INSERT INTO events (date, title, open_time, start_time, performance_time, location, price, image_data) VALUES (?,?,?,?,?,?,?,?)", (d,t,ot,st_t,pf_t,loc,pr,img_to_base64(img_file)), commit=True)
                st.rerun()
    
    evs = run_query("SELECT * FROM events ORDER BY date DESC")
    for ev in evs:
        with st.expander(f"📝 {ev['date']} | {ev['title']}"):
            with st.form(f"edit_{ev['id']}"):
                u_t = st.text_input("タイトル", value=ev['title'])
                if st.form_submit_button("更新"):
                    run_query("UPDATE events SET title=? WHERE id=?", (u_t, ev['id']), commit=True); st.rerun()
                if st.form_submit_button("🚨 削除"):
                    run_query("DELETE FROM events WHERE id=?", (ev['id'],), commit=True); st.rerun()

elif st.session_state.page == "admin_customers":
    st.markdown("### 👥 顧客管理")
    summary = run_query("SELECT e.date, e.title, SUM(r.people) as total FROM events e LEFT JOIN reservations r ON e.id = r.event_id GROUP BY e.id ORDER BY e.date DESC")
    st.table(summary)
    all_res = run_query("SELECT r.name, r.email, r.people, e.date, e.title FROM reservations r JOIN events e ON r.event_id = e.id ORDER BY e.date DESC")
    st.dataframe(all_res, use_container_width=True)

elif st.session_state.page == "admin_style":
    st.subheader("🎨 外観設定")
    with st.form("style"):
        bg = st.file_uploader("背景画像")
        tp = st.file_uploader("TOP画像")
        if st.form_submit_button("保存"):
            if bg: run_query("INSERT INTO site_info (key, value) VALUES ('bg_image', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (img_to_base64(bg),), commit=True)
            if tp: run_query("INSERT INTO site_info (key, value) VALUES ('top_image', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (img_to_base64(tp),), commit=True)
            st.rerun()
    if st.button("背景リセット"): run_query("DELETE FROM site_info WHERE key='bg_image'", commit=True); st.rerun()

elif st.session_state.page == "list":
    st.markdown('### SCHEDULE LIST')
    res = run_query_cached("SELECT date, title FROM events ORDER BY date ASC")
    for r in res:
        if st.button(f"{r['date']} | {r['title']}", use_container_width=True):
            st.session_state.selected_date = r['date']; st.session_state.page = "detail"; st.rerun()
