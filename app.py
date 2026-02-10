import streamlit as st
import sqlite3
import base64
import calendar as pycal
from datetime import datetime
import urllib.parse

# ───────────────────────────────
# 1. 接続先の自動判別
# ───────────────────────────────
USE_EXTERNAL_DB = "postgres" in st.secrets

# ───────────────────────────────
# 2. 共通DB操作関数（キャッシュで高速化）
# ───────────────────────────────
def get_db_connection():
    if USE_EXTERNAL_DB:
        import psycopg2
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

# 読み込みを高速化するためにキャッシュを使用（10分間保持）
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
            st.cache_data.clear() # 更新があったらキャッシュをクリア
            return None
        res = cur.fetchall()
        return [dict(row) for row in res]
    except Exception as e:
        st.error(f"DBエラーだぜ: {e}")
        return []
    finally:
        conn.close()

def img_to_base64(uploaded_file):
    if uploaded_file is not None:
        return base64.b64encode(uploaded_file.read()).decode()
    return None

# ───────────────────────────────
# 3. 初期化
# ───────────────────────────────
id_type = "SERIAL PRIMARY KEY" if USE_EXTERNAL_DB else "INTEGER PRIMARY KEY AUTOINCREMENT"
run_query('CREATE TABLE IF NOT EXISTS site_info (key TEXT PRIMARY KEY, value TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS events (id {id_type}, date TEXT, title TEXT, open_time TEXT, start_time TEXT, performance_time TEXT, price TEXT, location TEXT, image_data TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS reservations (id {id_type}, event_id INTEGER, name TEXT, people INTEGER, email TEXT, status TEXT DEFAULT \'active\')', commit=True)

# ───────────────────────────────
# 4. スタイル設定（シンプル＆高視認性）
# ───────────────────────────────
st.set_page_config(page_title="One Once Over", layout="wide")

def get_info(key, default=""):
    res = run_query_cached("SELECT value FROM site_info WHERE key=?", (key,))
    return res[0]['value'] if res else default

bg_img = get_info("bg_image", "")
top_img = get_info("top_image", "")

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Noto+Sans+JP:wght@700;900&display=swap');
    
    .stApp {{ 
        background-color: #121212; 
        {f'background-image: linear-gradient(rgba(18,18,18,0.8), rgba(18,18,18,0.8)), url(data:image/png;base64,{bg_img});' if bg_img else ''}
        background-size: cover; background-attachment: fixed;
    }}
    
    .main-title {{ font-family: 'Anton', sans-serif; font-size: clamp(40px, 12vw, 80px); color: #ff6600; text-shadow: 2px 2px 10px rgba(0,0,0,0.5); text-align: center; }}
    .sub-title {{ font-family: 'Noto Sans JP', sans-serif; font-size: 14px; color: #00ff00; text-align: center; letter-spacing: 2px; }}
    
    /* カード類をさらに見やすく */
    .detail-card {{ background: rgba(25, 25, 25, 0.95); padding: 20px; border-radius: 12px; border: 1px solid #333; }}
    .info-box {{ background: #1e1e1e; border-left: 4px solid #ff6600; padding: 12px; border-radius: 4px; color: #eee; }}
    .success-box {{ background: #1e1e1e; border-left: 4px solid #00ff00; padding: 12px; border-radius: 4px; color: #eee; }}

    .cal-table {{ width: 100%; border-collapse: collapse; background: rgba(0,0,0,0.7); }}
    .cal-td {{ border: 1px solid #444; height: 100px; vertical-align: top; padding: 5px; }}
    .event-badge {{ background: #ff6600; color: #fff; font-size: 10px; padding: 2px; border-radius: 3px; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; display: block; }}
    </style>
    """, unsafe_allow_html=True)

# ───────────────────────────────
# 5. メインナビゲーション
# ───────────────────────────────
for k in ['is_logged_in', 'page', 'selected_date', 'view_month', 'view_year']:
    if k not in st.session_state:
        st.session_state[k] = datetime.now().month if k == 'view_month' else datetime.now().year if k == 'view_year' else "top" if k == 'page' else False

with st.sidebar:
    if st.button("🏠 TOP"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    if st.button("📅 LIST"): st.session_state.page = "list"; st.rerun()
    if st.session_state.is_logged_in:
        st.divider()
        if st.button("🎸 ライブ管理"): st.session_state.page = "admin_events"; st.rerun()
        if st.button("👥 顧客名簿"): st.session_state.page = "admin_customers"; st.rerun()
        if st.button("🎨 デザイン"): st.session_state.page = "admin_style"; st.rerun()
        if st.button("Logout"): st.session_state.is_logged_in = False; st.rerun()
    else:
        with st.expander("Owner"):
            if st.text_input("Pass", type="password") == "owner123":
                st.session_state.is_logged_in = True; st.rerun()

# ───────────────────────────────
# 6. 各ページ処理
# ───────────────────────────────

if st.session_state.page == "top":
    st.markdown('<h1 class="main-title">One Once Over</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">LIVE RESERVATION SYSTEM</p>', unsafe_allow_html=True)
    
    # 月移動ナビ
    col_l, col_c, col_r = st.columns([1,2,1])
    with col_c:
        q_y, q_m = st.query_params.get("y"), st.query_params.get("m")
        if q_y and q_m: st.session_state.view_year, st.session_state.view_month = int(q_y), int(q_m)
        cur_y, cur_m = st.session_state.view_year, st.session_state.view_month
        st.markdown(f"<h3 style='text-align:center;'>{cur_y} / {cur_m:02d}</h3>", unsafe_allow_html=True)

    # カレンダー描画（ロジックは前回同様）
    cal = pycal.Calendar(0)
    month_days = cal.monthdayscalendar(cur_y, cur_m)
    rows = run_query_cached("SELECT date, title, image_data FROM events")
    live_map = { r['date']: r for r in rows }
    
    html = '<table class="cal-table"><tr>' + "".join([f'<th style="color:#888;">{d}</th>' for d in ["M","T","W","T","F","S","S"]]) + '</tr>'
    for week in month_days:
        html += '<tr>'
        for idx, day in enumerate(week):
            if day == 0: html += '<td></td>'
            else:
                d_str = f"{cur_y}-{cur_m:02d}-{day:02d}"
                html += f'<td class="cal-td"><a href="./?date={d_str}" target="_self" style="text-decoration:none; color:#fff;">{day}'
                if d_str in live_map:
                    html += f'<div class="event-badge">{live_map[d_str]["title"]}</div>'
                html += '</a></td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)
    
    if st.query_params.get("date"):
        st.session_state.selected_date = st.query_params.get("date")
        st.session_state.page = "detail"; st.rerun()

elif st.session_state.page == "detail":
    ev = run_query_cached("SELECT * FROM events WHERE date=?", (st.session_state.selected_date,))
    if ev:
        e = ev[0]
        st.markdown(f'<div class="detail-card">', unsafe_allow_html=True)
        st.header(f"🎸 {e['title']}")
        st.markdown(f"<p style='color:#00ff00;'>📅 {st.session_state.selected_date}</p>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1: st.markdown(f'<div class="info-box">📍 {e["location"]}<br>💰 {e["price"]}</div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="success-box">⏰ Open: {e["open_time"]}<br>🎸 Start: {e["start_time"]}</div>', unsafe_allow_html=True)
        
        st.divider()
        with st.form("res_form"):
            u_name = st.text_input("お名前（必須）")
            u_email = st.text_input("メールアドレス")
            u_num = st.number_input("人数", 1, 10, 1)
            if st.form_submit_button("予約を確定する"):
                if not u_name.strip():
                    st.error("名前を入れてくれなきゃ困るぜ！")
                else:
                    # 重複チェック & 自動結合
                    existing = run_query("SELECT id, people FROM reservations WHERE event_id=? AND email=?", (e['id'], u_email))
                    if existing and u_email.strip() != "":
                        new_total = existing[0]['people'] + u_num
                        run_query("UPDATE reservations SET people=? WHERE id=?", (new_total, existing[0]['id']), commit=True)
                        st.success(f"おっ、追加予約だな！合計 {new_total} 名で承ったぜ！")
                    else:
                        run_query("INSERT INTO reservations (event_id, name, people, email) VALUES (?,?,?,?)", (e['id'], u_name, u_num, u_email), commit=True)
                        st.success("予約完了だ！会場で待ってるぜ。")
                    st.balloons()
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == "admin_events":
    st.title("🛠 管理：ライブ予定")
    with st.expander("🆕 新規登録"):
        with st.form("new"):
            d = st.date_input("日付").strftime('%Y-%m-%d')
            t = st.text_input("タイトル")
            loc = st.text_input("場所")
            if st.form_submit_button("登録"):
                run_query("INSERT INTO events (date, title, location) VALUES (?,?,?)", (d, t, loc), commit=True); st.rerun()

    evs = run_query("SELECT * FROM events ORDER BY date DESC")
    for ev in evs:
        with st.expander(f"📝 {ev['date']} | {ev['title']}"):
            # 予約者の表示・編集・削除
            reserves = run_query("SELECT * FROM reservations WHERE event_id=?", (ev['id'],))
            for r in reserves:
                col1, col2, col3 = st.columns([3,1,1])
                col1.write(f"👤 {r['name']} ({r['email']})")
                col2.write(f"{r['people']}名")
                if col3.button("削除", key=f"del_{r['id']}"):
                    run_query("DELETE FROM reservations WHERE id=?", (r['id'],), commit=True)
                    st.rerun()
            if st.button("イベント自体を削除", key=f"dev_{ev['id']}", type="primary"):
                run_query("DELETE FROM events WHERE id=?", (ev['id'],), commit=True); st.rerun()

elif st.session_state.page == "admin_customers":
    st.title("👥 顧客名簿")
    data = run_query("""
        SELECT e.date, e.title, r.name, r.email, r.people 
        FROM reservations r JOIN events e ON r.event_id = e.id 
        ORDER BY e.date DESC
    """)
    st.dataframe(data, use_container_width=True)

elif st.session_state.page == "admin_style":
    st.title("🎨 デザイン設定")
    with st.form("s"):
        bg = st.file_uploader("背景画像")
        if st.form_submit_button("保存"):
            if bg: run_query("INSERT INTO site_info (key, value) VALUES ('bg_image', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (img_to_base64(bg),), commit=True)
            st.rerun()
    if st.button("リセット"): run_query("DELETE FROM site_info WHERE key='bg_image'", commit=True); st.rerun()

elif st.session_state.page == "list":
    st.title("SCHEDULE")
    res = run_query_cached("SELECT date, title FROM events ORDER BY date ASC")
    for r in res:
        if st.button(f"{r['date']} | {r['title']}", use_container_width=True):
            st.session_state.selected_date = r['date']; st.session_state.page = "detail"; st.rerun()
