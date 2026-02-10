import streamlit as st
import sqlite3
import os
import base64
import urllib.parse
import calendar as pycal
from datetime import datetime

# ───────────────────────────────
# 1. 接続先の自動判別スイッチ
# ───────────────────────────────
# .streamlit/secrets.toml に [postgres] があれば外部DBモードになるぜ
USE_EXTERNAL_DB = "postgres" in st.secrets

if USE_EXTERNAL_DB:
    import psycopg2
    from psycopg2.extras import DictCursor
    conn_info = "🌐 外部DB(Supabase)に接続中"
else:
    import sqlite3
    conn_info = "🏠 ローカルDB(SQLite)に接続中"

# ───────────────────────────────
# 2. 共通DB操作関数 (ハイブリッド仕様)
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
    # SQLプレースホルダ変換 (SQLite: ? / PostgreSQL: %s)
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
        # どのDBでも「名前」や「添字」でデータを取り出せるようにリスト化
        return [list(row) if not USE_EXTERNAL_DB else dict(row) for row in res]
    except Exception as e:
        st.error(f"DBエラーだぜ: {e}")
        return []
    finally:
        conn.close()

# ───────────────────────────────
# 3. テーブル初期化 (Supabase / SQLite 両対応版)
# ───────────────────────────────
id_type = "SERIAL PRIMARY KEY" if USE_EXTERNAL_DB else "INTEGER PRIMARY KEY AUTOINCREMENT"

run_query('CREATE TABLE IF NOT EXISTS site_info (key TEXT PRIMARY KEY, value TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS events (id {id_type}, date TEXT, title TEXT, description TEXT, open_time TEXT, start_time TEXT, price TEXT, location TEXT, image_path TEXT)', commit=True)
run_query(f'CREATE TABLE IF NOT EXISTS users (id {id_type}, email TEXT UNIQUE, password TEXT, name TEXT)', commit=True)

# ここがエラーの原因！PostgreSQL用に整理したぜ
if USE_EXTERNAL_DB:
    run_query(f'CREATE TABLE IF NOT EXISTS reservations (id {id_type}, event_id INTEGER, user_id INTEGER, name TEXT, people INTEGER, email TEXT, status TEXT DEFAULT \'active\')', commit=True)
else:
    run_query(f'CREATE TABLE IF NOT EXISTS reservations (id {id_type}, event_id INTEGER, user_id INTEGER, name TEXT, people INTEGER, email TEXT, status TEXT DEFAULT "active")', commit=True)

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
    # SQLiteはリストのリスト、Postgresはリストの辞書で返るのを考慮
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

# CSS適用
bg_img_base64 = get_info("bg_image", "")
bg_style = f'background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), url("data:image/png;base64,{bg_img_base64}");' if bg_img_base64 else 'background: #111;'
st.markdown("""
    <style>
    /* --- 基本のタイトル設定 --- */
    .main-title {
        font-family: 'Anton', sans-serif;
        font-size: 80px;
        color: #ff6600;
        text-shadow: 3px 3px 0px #fff;
        text-align: center;
        margin-bottom: 0;
        line-height: 1.1;
    }
    .sub-title {
        font-family: 'Noto Sans JP', sans-serif;
        font-size: 24px;
        color: #00ff00;
        font-weight: bold;
        text-align: center;
        margin-top: -10px;
    }

    /* --- スマホ（画面幅 768px 以下）用の調整 --- */
    @media (max-width: 768px) {
        .main-title {
            font-size: 45px; /* スマホではサイズを半分近くまで落とすぜ */
            text-shadow: 2px 2px 0px #fff;
        }
        .sub-title {
            font-size: 16px; /* サブタイトルも控えめに */
            margin-top: 0px;
        }
        /* カレンダーの文字がはみ出さないように調整 */
        .cal-table {
            font-size: 10px;
        }
        .event-badge {
            font-size: 8px;
            padding: 1px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# ───────────────────────────────
# 6. サイドバー
# ───────────────────────────────
with st.sidebar:
    st.info(conn_info)
    st.title("🎸 MENU")
    if st.button("🏠 TOPへ戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    if st.button("📅 ライブ予定一覧"): st.session_state.page = "list"; st.rerun()
    st.divider()

    if st.session_state.user_auth:
        st.success(f"Member: {st.session_state.user_auth['name']}")
        if st.button("マイページ"): st.session_state.page = "mypage"; st.rerun()
        if st.button("ログアウト"): st.session_state.user_auth = None; st.rerun()
    else:
        with st.expander("👤 メンバーログイン/登録"):
            t_log, t_reg = st.tabs(["ログイン", "新規登録"])
            with t_log:
                le = st.text_input("Email", key="u_le"); lp = st.text_input("Pass", type="password", key="u_lp")
                if st.button("Login"):
                    u = run_query("SELECT id, name, email FROM users WHERE email=? AND password=?", (le, lp))
                    if u:
                        d = u[0] if isinstance(u[0], dict) else {"id":u[0][0], "name":u[0][1], "email":u[0][2]}
                        st.session_state.user_auth = d; st.rerun()
            with t_reg:
                rn = st.text_input("名前"); re = st.text_input("メール"); rp = st.text_input("パスワード", type="password")
                if st.button("登録"):
                    run_query("INSERT INTO users (email, password, name) VALUES (?,?,?)", (re, rp, rn), commit=True)
                    st.success("登録完了だぜ！"); st.rerun()

    st.divider()
    if st.session_state.is_logged_in:
        st.warning("🛠 OWNER MODE")
        if st.button("オーナー名簿・管理"): st.session_state.page = "admin_users"; st.rerun()
        
        # 1. サイトデザイン編集
        with st.expander("🖼 サイトデザイン編集"):
            st.subheader("トップ画像の変更")
            new_top = st.file_uploader("新しいトップ画像を選択", type=['jpg', 'png'], key="top_up")
            if st.button("トップ画像を更新"):
                if new_top:
                    b64_top = base64.b64encode(new_top.read()).decode()
                    save_info("top_image_b64", b64_top)
                    st.success("トップ画像を更新したぜ！")
                    st.rerun()

            st.divider()
            st.subheader("背景画像の変更")
            new_bg = st.file_uploader("新しい背景画像を選択", type=['jpg', 'png'], key="bg_up")
            if st.button("背景画像を更新"):
                if new_bg:
                    b64_bg = base64.b64encode(new_bg.read()).decode()
                    save_info("bg_image", b64_bg)
                    st.success("背景を更新したぜ！")
                    st.rerun()

        # 2. ライブ登録（これが復活だ！）
        with st.expander("📅 ライブ情報の新規登録"):
            with st.form("add_live"):
                d = st.date_input("日付")
                t = st.text_input("ライブタイトル")
                loc = st.text_input("会場")
                op = st.text_input(" Open", value="18:30")
                stt = st.text_input("Start", value="19:00")
                play_time = st.text_input("出演時間", value="00:00 〜")
                pr = st.text_input("チケット料金", value="¥2,500 + 1D")
                ds = st.text_area("ライブ詳細・出演者など")
                img = st.file_uploader("フライヤー画像", type=['jpg', 'png'])
                
                if st.form_submit_button("この内容でライブを公開する"):

                    combined_desc = f"🎸出演時間：{play_time}\n\n{ds}"
                    # フライヤー画像があればローカルに保存（パスをDBへ）
                    p = f"img_{d.strftime('%Y%m%d')}.jpg" if img else ""
                    if img:
                        with open(p, "wb") as f:
                            f.write(img.getbuffer())
                    
                    run_query("""
                        INSERT INTO events (date, title, description, open_time, start_time, price, location, image_path) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (d.strftime("%Y-%m-%d"), t, ds, op, stt, pr, loc, p), commit=True)
                    st.success(f"{t} の登録が完了したぜ！カレンダーを見てみろよ！")

        if st.button("オーナーログアウト"): 
            st.session_state.is_logged_in = False
            st.rerun()

        # 3. ライブ情報の編集・削除 (NEW!)
        with st.expander("📝 登録済みライブの編集・削除"):
            all_events = run_query("SELECT * FROM events ORDER BY date DESC")
            if all_events:
                # 辞書形式に変換（扱いやすくするため）
                event_list = [dict(r) if USE_EXTERNAL_DB else {"id":r[0],"date":r[1],"title":r[2],"description":r[3],"open_time":r[4],"start_time":r[5],"price":r[6],"location":r[7],"image_path":r[8]} for r in all_events]
                
                # セレクトボックスで編集したいライブを選択
                event_labels = [f"{e['date']} | {e['title']}" for e in event_list]
                selected_label = st.selectbox("編集するライブを選択", event_labels)
                
                # 選択されたライブのデータを抽出
                edit_data = next(e for e in event_list if f"{e['date']} | {e['title']}" == selected_label)
                
                # --- 編集用フォーム ---
                with st.form("edit_live_form"):
                    st.info(f"現在「{edit_data['title']}」を編集してるぜ")
                    new_d = st.date_input("日付", value=datetime.strptime(edit_data['date'], '%Y-%m-%d'))
                    new_t = st.text_input("ライブタイトル", value=edit_data['title'])
                    new_loc = st.text_input("会場", value=edit_data['location'])
                    
                    new_op = st.text_input("OPEN", value=edit_data['open_time'])
                    new_stt = st.text_input("START", value=edit_data['start_time'])
                    
                    # 出演時間をdescriptionから分離して表示
                    desc_parts = edit_data['description'].split('\n\n', 1)
                    current_play_time = desc_parts[0].replace("🎸出演時間：", "") if desc_parts[0].startswith("🎸") else "00:00 〜"
                    current_ds = desc_parts[1] if len(desc_parts) > 1 else desc_parts[0]
                    
                    new_play_time = st.text_input("出演時間", value=current_play_time)
                    new_pr = st.text_input("チケット料金", value=edit_data['price'])
                    new_ds = st.text_area("ライブ詳細・備考", value=current_ds)
                    
                    col_edit, col_del = st.columns([1, 1])
                    with col_edit:
                        if st.form_submit_button("✅ 変更を保存する"):
                            # 合体させて上書き
                            updated_desc = f"🎸出演時間：{new_play_time}\n\n{new_ds}"
                            run_query("""
                                UPDATE events 
                                SET date=%s, title=%s, description=%s, open_time=%s, start_time=%s, price=%s, location=%s 
                                WHERE id=%s
                            """, (new_d.strftime("%Y-%m-%d"), new_t, updated_desc, new_op, new_stt, new_pr, new_loc, edit_data['id']), commit=True)
                            st.success("情報を更新したぜ！")
                            st.rerun()
                            
                # 削除ボタンはフォームの外に配置（誤操作防止だ！）
                if st.button("🗑️ このライブを完全に削除する", key="del_btn"):
                    run_query("DELETE FROM events WHERE id=%s", (edit_data['id'],), commit=True)
                    st.error("削除したぜ。あばよ！")
                    st.rerun()
            else:
                st.write("登録されたライブはないぜ。")
                    
    else:
        with st.expander("🛠 管理者"):
            opw = st.text_input("Admin Pass", type="password")
            if st.button("Admin Login"):
                if opw == "owner123": st.session_state.is_logged_in = True; st.rerun()

# ───────────────────────────────
# 7. メインロジック
# ───────────────────────────────
if st.session_state.page == "top":
    st.markdown("""
    <style>
    /* 1. Google Fonts 読み込み */
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Noto+Sans+JP:wght@900&display=swap');

    /* 2. 基本のタイトル設定 */
    .main-title {
        font-family: 'Anton', sans-serif;
        font-size: 80px;
        color: #ff6600;
        text-shadow: 3px 3px 0px #fff;
        text-align: center;
        margin-bottom: 0;
        line-height: 1.1;
    }
    .sub-title {
        font-family: 'Noto Sans JP', sans-serif;
        font-size: 24px;
        color: #00ff00;
        font-weight: bold;
        text-align: center;
        margin-top: -10px;
    }

    /* 3. カレンダーの基本デザイン（これが消えてたはずだ！） */
    .cal-table { width: 100%; border-collapse: collapse; background: #000; color: #fff; }
    .cal-header { background: #333; color: #fff; padding: 10px; text-align: center; border: 1px solid #444; }
    .cal-td { border: 1px solid #444; width: 14%; height: 100px; vertical-align: top; position: relative; padding: 5px; }
    .cal-link { text-decoration: none; color: inherit; display: block; width: 100%; height: 100%; }
    .day-num { font-weight: bold; font-size: 18px; color: #fff; }
    .day-holiday { color: #ff4b4b !important; }
    .day-sat { color: #4b4bff !important; }
    .event-badge { background: #ff6600; color: #fff; font-size: 10px; padding: 3px; border-radius: 3px; margin-top: 5px; text-align: center; }
    .cal-img { width: 100%; height: auto; border-radius: 5px; margin-top: 5px; }

    /* 4. 【重要】スマホ専用の調整（画面幅 768px 以下） */
    @media (max-width: 768px) {
        .main-title {
            font-size: 40px !important; /* スマホではタイトルを小さく */
            text-shadow: 2px 2px 0px #fff;
        }
        .sub-title {
            font-size: 14px !important;
            margin-top: 0px;
        }
        .cal-td {
            height: 60px; /* スマホでは高さを抑える */
            padding: 2px;
        }
        .day-num {
            font-size: 12px;
        }
        .event-badge {
            font-size: 7px;
            padding: 1px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # --- 【ここが追加：トップ画像表示】 ---
    top_img_b64 = get_info("top_image_b64", "")
    if top_img_b64:
        # DBに画像がある場合はそれを表示
        st.image(f"data:image/jpeg;base64,{top_img_b64}", use_container_width=True)
    else:
        # DBに画像がない場合のバックアップ
        if os.path.exists("top_hero.jpg"):
            st.image("top_hero.jpg", use_container_width=True)
    
    st.divider() # タイトル・画像とカレンダーの区切り

    col_p, col_c, col_n = st.columns([1, 4, 1])
    with col_p:
        if st.button("◀ 前月"):
            st.session_state.view_month -= 1
            if st.session_state.view_month == 0: st.session_state.view_month = 12; st.session_state.view_year -= 1
            st.rerun()
    with col_c: st.markdown(f"<h2 style='text-align: center; color:#39FF14;'>{st.session_state.view_year}年 {st.session_state.view_month:02d}月</h2>", unsafe_allow_html=True)
    with col_n:
        if st.button("次月 ▶"):
            st.session_state.view_month += 1
            if st.session_state.view_month == 13: st.session_state.view_month = 1; st.session_state.view_year += 1
            st.rerun()

    cal = pycal.Calendar(0)
    month_days = cal.monthdayscalendar(st.session_state.view_year, st.session_state.view_month)
    rows = run_query("SELECT date, title, image_path FROM events")
    live_data = { (r[0] if isinstance(r, list) else r['date']): r for r in rows }

    html = '<table class="cal-table"><tr>'
    for d_name in ["月", "火", "水", "木", "金", "土", "日"]: html += f'<th class="cal-header">{d_name}</th>'
    html += '</tr>'
    
    for week in month_days:
        html += '<tr>'
        for idx, day in enumerate(week):
            if day == 0: html += '<td style="border:none;"></td>'
            else:
                d_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day:02d}"
                hol = get_holiday(st.session_state.view_year, st.session_state.view_month, day)
                cls = "day-holiday" if (hol or idx == 6) else "day-sat" if idx == 5 else ""
                html += f'<td class="cal-td {cls}"><a href="./?date={d_str}" target="_self" class="cal-link">'
                html += f'<span class="day-num">{day}</span>'
                if hol: html += f'<div style="font-size:9px;">{hol}</div>'
                if d_str in live_data:
                    title = live_data[d_str][1] if isinstance(live_data[d_str], list) else live_data[d_str]['title']
                    img_p = live_data[d_str][2] if isinstance(live_data[d_str], list) else live_data[d_str]['image_path']
                    html += f'<div class="event-badge">{title}</div>'
                    if img_p and os.path.exists(img_p):
                        with open(img_p, "rb") as f:
                            img_b64 = base64.b64encode(f.read()).decode()
                            html += f'<img src="data:image/jpeg;base64,{img_b64}" class="cal-img">'
                html += '</a></td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

    if st.query_params.get("date"):
        st.session_state.selected_date = st.query_params.get("date")
        st.session_state.page = "detail"; st.rerun()

elif st.session_state.page == "detail":
    if st.button("← TOPへ戻る"): st.session_state.page = "top"; st.query_params.clear(); st.rerun()
    ev = run_query("SELECT * FROM events WHERE date=?", (st.session_state.selected_date,))
    if ev:
        e = ev[0] # dict or list
        if isinstance(e, list): e = {"id":e[0], "title":e[2], "description":e[3], "open_time":e[4], "start_time":e[5], "price":e[6], "location":e[7], "image_path":e[8]}
        st.markdown(f'<span class="huge-title" style="font-size:60px !important;">{e["title"]}</span>', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1])
        with col1:
            if e["image_path"] and os.path.exists(e["image_path"]): st.image(e["image_path"], use_container_width=True)
        with col2:
            st.markdown(f"### 📅 {st.session_state.selected_date}")
            st.markdown(f"### 📍 {e['location']}")
            
            # --- Google Mapリンクボタン ---
            map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(e['location'])}"
            st.link_button("🗺️ Google Mapで会場を見る", map_url)
            # ----------------------------

            st.markdown(f"**OPEN:** {e['open_time']} / **START:** {e['start_time']}" )    
            st.divider()
            st.markdown("####  ⚡️ LIVE INFO ⚡️")
            st.write(e["description"])
        
        with st.form("res_form"):
            st.subheader("🎟 予約フォーム")
            u_n = st.session_state.user_auth['name'] if st.session_state.user_auth else ""
            u_e = st.session_state.user_auth['email'] if st.session_state.user_auth else ""
            n = st.text_input("お名前", value=u_n); p = st.number_input("人数", 1, 10, 1); m = st.text_input("メール", value=u_e)
            if st.form_submit_button("予約確定"):
                uid = st.session_state.user_auth['id'] if st.session_state.user_auth else None
                run_query("INSERT INTO reservations (event_id, user_id, name, people, email) VALUES (?,?,?,?,?)", (e['id'], uid, n, p, m), commit=True)
                st.success("予約完了だぜ！")

elif st.session_state.page == "list":
    st.markdown('<span class="huge-title" style="font-size:60px !important;">SCHEDULE</span>', unsafe_allow_html=True)
    res = run_query("SELECT date, title, location FROM events ORDER BY date ASC")
    for r in res:
        d, t, l = (r[0], r[1], r[2]) if isinstance(r, list) else (r['date'], r['title'], r['location'])
        if st.button(f"{d} | {t} | 📍 {l}", use_container_width=True):
            st.session_state.selected_date = d; st.session_state.page = "detail"; st.rerun()

elif st.session_state.page == "admin_users":
    st.markdown('<span class="huge-title" style="font-size:60px !important;">ADMIN: LIST</span>', unsafe_allow_html=True)
    res = run_query("SELECT r.id, e.date, e.title, r.name, r.people FROM reservations r JOIN events e ON r.event_id = e.id ORDER BY e.date DESC")
    for r in res:
        v = list(r.values()) if isinstance(r, dict) else r
        st.write(f"📅 {v[1]} : {v[3]} 様 ({v[4]}名) - {v[2]}")
