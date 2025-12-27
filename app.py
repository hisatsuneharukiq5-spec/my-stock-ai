import streamlit as st
import google.generativeai as genai
import requests
import datetime
import fitz  # PyMuPDF
import time
import urllib.parse

# --- 1. 初期設定 ---
if "GEMINI_API_KEY" in st.secrets:
    GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    GENAI_API_KEY = "YOUR_LOCAL_API_KEY"

genai.configure(api_key=GENAI_API_KEY)

# --- 2. 使えるAIモデルを自動で選ぶ関数 ---
def get_working_model():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 429エラーを避けるため、無料枠が安定している 1.5-flash を一番上に持ってきました
        target_models = [
            "models/gemini-1.5-flash", 
            "models/gemini-1.5-pro",
            "models/gemini-2.0-flash-exp" # 2.0は最後に試す
        ]
        
        for name in target_models:
            if name in available_models:
                return name
        return available_models[0] if available_models else None
    except:
        return None

# --- 3. AI分析関数 ---
def analyze_pdf(pdf_bytes, model_name):
    try:
        with st.spinner("AIが資料を読み込んで分析中..."):
            text = ""
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc: text += page.get_text()
            
            if not text.strip():
                st.error("PDFから文字を抽出できません。画像形式のPDFの可能性があります。")
                return

            model = genai.GenerativeModel(model_name)
            prompt = f"プロの証券アナリストとして、以下の決算短信から『業績のポイント』と『将来性』を3点ずつ、非常に分かりやすく要約して下さい。\n\n{text[:30000]}"
            response = model.generate_content(prompt)
            
            st.success("✅ 分析が完了しました！")
            st.markdown(response.text)
    except Exception as e:
        st.error(f"分析エラー: {str(e)}")

# --- 4. EDINET検索関数（ブロック通知付き） ---
def get_kessan_pdf(ticker_code):
    raw_code = str(ticker_code).strip()
    target_code = raw_code + "0" if len(raw_code) == 4 else raw_code
    HEADERS = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}
    
    for i in range(14): # 直近2週間に絞って素早く検索
        date = (datetime.date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents.json?date={date}&type=2"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for doc in data.get("results", []):
                    if target_code in str(doc.get("secCode", "")) and "決算短信" in str(doc.get("docDescription", "")):
                        pdf_url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents/{doc["docID"]}"
                        pdf_res = requests.get(pdf_url, params={"type": 2}, headers=HEADERS)
                        return pdf_res.content, doc["docDescription"]
            elif res.status_code == 403: return "BLOCKED", None
        except: continue
    return None, None

# --- 5. メイン画面 ---
st.set_page_config(page_title="AI株アナライザー", layout="wide")
st.title("📈 AI決算アナライザー")

working_model = get_working_model()

# サイドバーに説明
with st.sidebar:
    st.info("💡 **使い分けのコツ**\n\nお役所(EDINET)のサーバーは制限が厳しいため、自動検索がエラーになることが多いです。その場合は「PDFをアップロード」をご利用ください。")

tab1, tab2 = st.tabs(["🔍 コードで検索 (実験中)", "📤 PDFを直接分析 (推奨)"])

with tab1:
    ticker = st.text_input("証券コード (4桁)", placeholder="例: 7203", key="ticker_input")
    if st.button("最新決算を自動検索"):
        pdf_data, title = get_kessan_pdf(ticker)
        if pdf_data == "BLOCKED":
            st.error("現在EDINET側でブロックされています。下のボタンからPDFをダウンロードして、右のタブで読み込ませてください。")
            # Google検索リンクを生成
            search_query = urllib.parse.quote(f"{ticker} 決算短信 PDF")
            st.markdown(f'[![GoogleでPDFを探す](https://img.shields.io/badge/Google検索-%E2%86%92-blue?style=for-the-badge)](https://www.google.com/search?q={search_query})')
        elif pdf_data:
            st.info(f"発見: {title}")
            analyze_pdf(pdf_data, working_model)
        else:
            st.warning("直近の決算が見つかりませんでした。")

with tab2:
    st.subheader("PDFをアップロードして分析")
    st.write("iPad/スマホでダウンロードしたPDFを選択してください。")
    uploaded_file = st.file_uploader("決算短信のPDF", type="pdf")
    if uploaded_file and working_model:
        analyze_pdf(uploaded_file.read(), working_model)

