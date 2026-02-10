import streamlit as st
import sqlite3
import os
import smtplib
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
# 3. メール送信関数
# ───────────────────────────────
def send_email(to_email, subject, body):
    try:
        smtp_user = st.secrets["email"]["user"]
        smtp_pass = st.secrets["email"]["password"]
        
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"メール送信失敗したぜ: {e}")
        return False

# ───────────────────────────────
# 4. テーブル初期化
# ───────────────────────────────
id_type = "SERIAL PRIMARY KEY" if USE_EXTERNAL_DB else "INTEGER PRIMARY KEY AUTOINCREMENT"
run_query('CREATE TABLE IF NOT EXISTS site_info (key TEXT PRIMARY KEY, value TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS events (id {id_type}, date TEXT, title TEXT, description TEXT, open_time TEXT, start_time TEXT, price TEXT, location TEXT, image_path TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS reservations (id {id_type}, event_id INTEGER, name TEXT, people INTEGER, email TEXT, status TEXT DEFAULT \'active\')', commit=True)

# ───────────────────────────────
# 5. ヘルパー関数
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

# ───────────────────────────────
# 6. UI設定 & セッション
# ───────────────────────────────
st.set_page_config(page_title="One Once Over", layout="wide")

for k in ['is_logged_in', 'page', 'selected_date', 'view_month', 'view_year']:
    if k not in st.session_state:
        if k == 'view_month': st.session_state[k] = datetime.now().month
        elif k == 'view_year': st.session_state[k] = datetime.now().year
        elif k == 'page': st.session_state[k] = "top"
        else: st.session_state[k] = None if k == 'selected_date' else False

# --- 🎨 共通CSS (はみ出し防止 & モバイル最適化) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Noto+Sans+JP:wght@900&display=swap');
    .block-container { padding: 1rem 0.5rem !important; }
    
    /* タイトルはみ出し対策 */
    .main-title { 
        font-family: 'Anton', sans-serif !important; 
        font-size: clamp(35px, 12vw, 80px) !important; 
        color: #ff6600 !important; 
        text-shadow: 2px 2px 0px #fff !important; 
        text-align: center !important; 
        margin: 0 !important;
        overflow-wrap: break-word; word-wrap: break-word;
        line-height: 1.1;
    }
    .sub-title { font-family: 'Noto Sans JP', sans-serif !important; font-size: 14px !important; color: #00ff00 !important; text-align: center !important; margin-bottom: 10px !important; }

    .cal-table { width: 100% !important; border-collapse: collapse !important; table-layout: fixed !important; background: #000 !important; }
    .cal-header { background: #333 !important; color: #fff !important; font-size: 11px !important; padding: 4px 0 !important; border: 1px solid #444 !important; }
    .cal-td { border: 1px solid #444 !important; height: clamp(65px, 15vh, 100px) !important; vertical-align: top !important; padding: 2px !important; }
    
    .day-num { font-weight: bold !important; font-size: 14px !important; color: #fff !important; }
    .day-holiday, .day-holiday .day-num { color: #ff4b4b !important; }
    .day-sat, .day-sat .day-num { color: #4b4bff !important; }
    
    .event-badge { 
        background: #ff6600 !important; color: #fff !important; font-size: 9px !important; 
        padding: 1px 2px !important; border-radius: 2px !important; margin-top: 2px !important; 
        white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
        display: block !important; width: 100% !important;
    }

    .nav-container {
        display: flex; justify-content: space-between; align-items: center;
        width: 100%; background: #111; border: 1px solid #00ff00; border-radius: 8px;
        margin-bottom: 8px; height: 45px;
    }
    .nav-btn { flex: 1; text-align: center; color: #00ff00 !important; text-decoration: none !important; font-weight: bold; font-size: 12px; line-height: 45px; }
    .nav-center { flex: 1.5; text-align: center; color: #fff; font-family: 'Anton', sans-serif; font-size: 16px; }
    </style>
    """, unsafe_allow_html=True)

# ───────────────────────────────
# 7. サイドバー
# ───────────────────────────────
with st.sidebar:
    st.info(conn_info)
    if st.button("🏠 TOPへ戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    if st.button("📅 予定一覧"): st.session_state.page = "list"; st.rerun()
    
    if st.session_state.is_logged_in:
        st.warning("🛠 OWNER MODE")
        if st.button("ライブ予定の管理/登録"): st.session_state.page = "admin_events"; st.rerun()
        if st.button("オーナーログアウト"): st.session_state.is_logged_in = False; st.rerun()
    else:
        with st.expander("🛠 管理者"):
            opw = st.text_input("Pass", type="password")
            if st.button("Login"):
                if opw == "owner123": st.session_state.is_logged_in = True; st.rerun()

# ───────────────────────────────
# 8. メインロジック
# ───────────────────────────────

# TOPページ
if st.session_state.page == "top":
    st.markdown('<h1 class="main-title">One Once Over</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">- ライブ予約サイト -</p>', unsafe_allow_html=True)

    # クエリパラメータ同期
    q_year, q_month = st.query_params.get("y"), st.query_params.get("m")
    if q_year and q_month:
        st.session_state.view_year, st.session_state.view_month = int(q_year), int(q_month)

    # ナビ
    p_year, p_month = (st.session_state.view_year, st.session_state.view_month - 1) if st.session_state.view_month > 1 else (st.session_state.view_year - 1, 12)
    n_year, n_month = (st.session_state.view_year, st.session_state.view_month + 1) if st.session_state.view_month < 12 else (st.session_state.view_year + 1, 1)
    
    st.markdown(f"""<div class="nav-container">
        <a href="./?y={p_year}&m={p_month}" target="_self" class="nav-btn">◀ PREV</a>
        <div class="nav-center">{st.session_state.view_year} / {st.session_state.view_month:02d}</div>
        <a href="./?y={n_year}&m={n_month}" target="_self" class="nav-btn">NEXT ▶</a>
    </div>""", unsafe_allow_html=True)

    # カレンダー
    cal = pycal.Calendar(0)
    month_days = cal.monthdayscalendar(st.session_state.view_year, st.session_state.view_month)
    rows = run_query("SELECT date, title FROM events")
    live_data = { (r[0] if isinstance(r, list) else r['date']): r for r in rows }

    html = '<table class="cal-table"><tr>' + "".join([f'<th class="cal-header">{d}</th>' for d in ["月","火","水","木","金","土","日"]]) + '</tr>'
    for week in month_days:
        html += '<tr>'
        for idx, day in enumerate(week):
            if day == 0: html += '<td style="border:none; background:transparent;"></td>'
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

# 詳細ページ（予約機能）
elif st.session_state.page == "detail":
    if st.button("← TOP"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    ev = run_query("SELECT * FROM events WHERE date=?", (st.session_state.selected_date,))
    if ev:
        e = ev[0]
        if isinstance(e, list): e = {"id":e[0], "date":e[1], "title":e[2], "open_time":e[4], "start_time":e[5], "location":e[7]}
        st.markdown(f'## {e["title"]}')
        st.write(f"📅 {e['date']} | 📍 {e['location']}")
        st.write(f"⏰ Open: {e['open_time']} / Start: {e['start_time']}")
        
        with st.form("res_form"):
            u_name = st.text_input("お名前")
            u_email = st.text_input("メールアドレス（任意：詳細が届きます）")
            u_num = st.number_input("人数", 1, 10, 1)
            if st.form_submit_button("予約を確定する"):
                run_query("INSERT INTO reservations (event_id, name, people, email) VALUES (?,?,?,?)", (e['id'], u_name, u_num, u_email), commit=True)
                
                # メール内容作成
                mail_body = f"{u_name}様\nご予約ありがとうございます！\n\n【詳細】\nイベント: {e['title']}\n日時: {e['date']}\n場所: {e['location']}\n時間: Open {e['open_time']} / Start {e['start_time']}\n人数: {u_num}名\n\n当日お待ちしております！"
                
                # ユーザーへ送信
                if u_email: send_email(u_email, f"【予約完了】{e['title']}", mail_body)
                # オーナーへ通知
                send_email("o.oneonceover@gmail.com", "【新規予約あり】", f"予約が入ったぞ！\n名前: {u_name}\nイベント: {e['title']}\n人数: {u_num}\n連絡先: {u_email}")
                
                st.success("予約完了だ！メールを確認してくれ。")

# 予定一覧
elif st.session_state.page == "list":
    st.markdown('### SCHEDULE')
    res = run_query("SELECT date, title FROM events ORDER BY date ASC")
    for r in res:
        d, t = (r[0], r[1]) if isinstance(r, list) else (r['date'], r['title'])
        if st.button(f"{d} | {t}", use_container_width=True):
            st.session_state.selected_date = d; st.session_state.page = "detail"; st.rerun()

# オーナー管理ページ（登録・編集・削除）
elif st.session_state.page == "admin_events":
    st.markdown("### 🛠 ライブ予定管理")
    
    with st.expander("🆕 新規登録"):
        with st.form("new_event"):
            d = st.date_input("日付").strftime('%Y-%m-%d')
            t = st.text_input("タイトル")
            ot = st.text_input("開場時間 (例 18:00)")
            st_t = st.text_input("開演時間 (例 18:30)")
            loc = st.text_input("場所")
            pr = st.text_input("料金")
            if st.form_submit_button("登録"):
                run_query("INSERT INTO events (date, title, open_time, start_time, location, price) VALUES (?,?,?,?,?,?)", (d,t,ot,st_t,loc,pr), commit=True)
                st.success("登録したぜ！"); st.rerun()

    st.markdown("---")
    evs = run_query("SELECT * FROM events ORDER BY date DESC")
    for ev in evs:
        if isinstance(ev, list): ev = {"id":ev[0], "date":ev[1], "title":ev[2], "open_time":ev[4], "start_time":ev[5], "location":ev[7]}
        with st.expander(f"📝 {ev['date']} | {ev['title']}"):
            with st.form(f"edit_{ev['id']}"):
                new_t = st.text_input("タイトル", value=ev['title'])
                new_ot = st.text_input("開場", value=ev['open_time'])
                new_st = st.text_input("開演", value=ev['start_time'])
                new_loc = st.text_input("場所", value=ev['location'])
                col1, col2 = st.columns(2)
                if col1.form_submit_button("更新"):
                    run_query("UPDATE events SET title=?, open_time=?, start_time=?, location=? WHERE id=?", (new_t, new_ot, new_st, new_loc, ev['id']), commit=True)
                    st.success("更新完了！"); st.rerun()
                if col2.form_submit_button("🚨 削除"):
                    run_query("DELETE FROM events WHERE id=?", (ev['id'],), commit=True)
                    st.error("消したぜ！"); st.rerun()
