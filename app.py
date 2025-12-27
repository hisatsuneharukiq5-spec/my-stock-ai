import streamlit as st
import google.generativeai as genai
import requests
import datetime
import fitz
import time

# --- 1. 設定 ---
GENAI_API_KEY = "AIzaSyDvs6cA3YGB4K2xUvJQzxAL1eKchtMnnrQ"  # ←ここをご自身のキーに書き換えてください
genai.configure(api_key=GENAI_API_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

# --- 2. AIモデルを自動で選ぶ関数 (IMG_3065で成功した機能) ---
def get_working_model():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if not available_models: return None
        for name in available_models:
            if 'flash' in name: return name
        return available_models[0]
    except:
        return None

# --- 3. AI分析を実行する関数 ---
def analyze_pdf(pdf_bytes, model_name):
    try:
        with st.spinner(f"AI({model_name})が分析中..."):
            text = ""
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc: text += page.get_text()
            
            if not text.strip():
                st.error("PDFから文字を読み取れませんでした。")
                return

            model = genai.GenerativeModel(model_name)
            prompt = f"以下の決算資料を読み、投資家向けに『経営の現状』と『将来性』を整理して要約してください。\n\n{text[:30000]}"
            response = model.generate_content(prompt)
            st.markdown(f"### 🤖 AI分析結果")
            st.markdown(response.text)
    except Exception as e:
        st.error(f"分析エラー: {str(e)}")

# --- 4. EDINETから自動でPDFを探す関数 (強化版) ---
def get_kessan_pdf(ticker_code):
    raw_code = str(ticker_code).strip()
    # 5桁（末尾0）に変換
    target_code = raw_code + "0" if len(raw_code) == 4 else raw_code
    
    # 直近45日分を検索
    for i in range(45):
        date = (datetime.date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents.json?date={date}&type=2"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for doc in data.get("results", []):
                    # 証券コードが一致し、かつ「決算短信」という文字が含まれるものを探す
                    if target_code in str(doc.get("secCode", "")) and "決算短信" in str(doc.get("docDescription", "")):
                        doc_id = doc["docID"]
                        pdf_url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents/{doc_id}"
                        pdf_res = requests.get(pdf_url, params={"type": 2}, headers=HEADERS)
                        return pdf_res.content, doc["docDescription"]
            elif res.status_code == 403:
                return "BLOCKED", None
        except:
            continue
        time.sleep(0.3) # サーバーに負担をかけないよう待機
    return None, None

# --- 5. 画面表示 (UI) ---
st.set_page_config(page_title="株AIアナライザー", layout="wide")
st.title("📈 株AIアナライザー")

# AIの接続確認
working_model = get_working_model()
if working_model:
    st.success(f"✅ AI準備完了: {working_model}")
else:
    st.error("❌ AIに接続できません。APIキーを確認してください。")

# タブで機能を分ける
tab1, tab2 = st.tabs(["証券コードで分析", "PDFアップロードで分析"])

with tab1:
    st.subheader("銘柄コードを入れるだけ！")
    ticker = st.text_input("証券コードを入力（例：7203）", max_chars=4)
    if st.button("最新の決算を自動分析"):
        if not ticker:
            st.warning("コードを入力してください。")
        else:
            pdf_data, title = get_kessan_pdf(ticker)
            if pdf_data == "BLOCKED":
                st.error("EDINETのサーバーからアクセスを拒否されました。しばらく時間を置くか、スマホのテザリングに切り替えてみてください。")
            elif pdf_data:
                st.info(f"書類を発見しました: {title}")
                analyze_pdf(pdf_data, working_model)
            else:
                st.warning("直近45日以内に『決算短信』が見つかりませんでした。時期を変えるか、別の銘柄でお試しください。")

with tab2:
    st.subheader("手元のPDFを直接分析")
    uploaded_file = st.file_uploader("決算短信のPDFを選択", type="pdf")
    if uploaded_file and working_model:
        analyze_pdf(uploaded_file.read(), working_model)