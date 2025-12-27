import streamlit as st
import google.generativeai as genai
import requests
import datetime
import fitz  # PyMuPDF
import time

# --- 1. セキュリティ設定（APIキー） ---
# Streamlit Cloudの「Secrets」からキーを読み込みます
if "GEMINI_API_KEY" in st.secrets:
    GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    # ローカル（PC）実行用の予備設定
    GENAI_API_KEY = "AIzaSyDvs6cA3YGB4K2xUvJQzxAL1eKchtMnnrQ"

genai.configure(api_key=GENAI_API_KEY)

# --- 2. 使えるAIモデルを自動で選ぶ関数 ---
def get_working_model():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 最新のflashモデルを優先的に探す
        for name in ["models/gemini-2.0-flash", "models/gemini-1.5-flash"]:
            if name in available_models:
                return name
        return available_models[0] if available_models else None
    except:
        return None

# --- 3. AI分析を実行する関数 ---
def analyze_pdf(pdf_bytes, model_name):
    try:
        with st.spinner("AIが資料を読み込んでいます..."):
            # PDFからテキストを抽出
            text = ""
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text()
            
            if not text.strip():
                st.error("PDFから文字を読み取れませんでした（画像形式の可能性があります）。")
                return

            # AIへ依頼
            model = genai.GenerativeModel(model_name)
            prompt = (
                "あなたはプロの証券アナリストです。提供された決算短信を読み、"
                "投資家が知るべき『現在の経営成績』と『今後の成長性』を、"
                "それぞれ3つのポイントで、中学生でもわかるように要約してください。"
                f"\n\n資料内容:\n{text[:30000]}"
            )
            response = model.generate_content(prompt)
            
            st.markdown("---")
            st.markdown(f"### 🤖 AI分析結果 (使用モデル: {model_name})")
            st.markdown(response.text)
    except Exception as e:
        st.error(f"分析中にエラーが発生しました: {str(e)}")

# --- 4. EDINETからPDFを探す関数（ブロック対策版） ---
def get_kessan_pdf(ticker_code):
    raw_code = str(ticker_code).strip()
    target_code = raw_code + "0" if len(raw_code) == 4 else raw_code
    
    # ブラウザからのアクセスに偽装してブロックを回避するヘッダー
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://disclosure.edinet-fsa.go.jp/"
    }

    # 直近30日間を探索
    for i in range(30):
        date = (datetime.date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents.json?date={date}&type=2"
        try:
            time.sleep(0.5) # サーバーへの負荷を抑える
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                data = res.json()
                for doc in data.get("results", []):
                    # 証券コードが一致し、かつ「決算短信」が含まれるものを探す
                    if target_code in str(doc.get("secCode", "")) and "決算短信" in str(doc.get("docDescription", "")):
                        doc_id = doc["docID"]
                        pdf_url = f"https://disclosure.edinet-fsa.go.jp/api/v1/documents/{doc_id}"
                        time.sleep(0.5)
                        pdf_res = requests.get(pdf_url, params={"type": 2}, headers=HEADERS)
                        return pdf_res.content, doc["docDescription"]
            elif res.status_code == 403:
                return "BLOCKED", None
        except:
            continue
    return None, None

# --- 5. メイン画面（UI） ---
st.set_page_config(page_title="株AIアナライザー", page_icon="📈", layout="wide")

st.title("📈 日本株AI決算アナライザー")
st.caption("証券コードを入れるか、PDFをドロップするだけでAIが分析します")

# AI接続確認
working_model = get_working_model()
if working_model:
    st.success(f"✅ AI準備完了 ({working_model})")
else:
    st.error("❌ AIに接続できません。SecretsのAPIキー設定を確認してください。")

# タブの作成
tab1, tab2 = st.tabs(["🔍 コードで自動検索", "📤 PDFをアップロード"])

with tab1:
    st.subheader("銘柄コードで分析")
    ticker = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)
    if st.button("最新の決算を分析する"):
        if not ticker:
            st.warning("コードを入力してください。")
        else:
            pdf_data, title = get_kessan_pdf(ticker)
            if pdf_data == "BLOCKED":
                st.error("現在、EDINETサーバーからアクセス制限を受けています。時間をおくか、下の『PDFをアップロード』タブから手動でファイルを読み込ませてください。")
            elif pdf_data:
                st.info(f"書類を発見しました: {title}")
                analyze_pdf(pdf_data, working_model)
            else:
                st.warning("直近30日以内に『決算短信』が見つかりませんでした。")

with tab2:
    st.subheader("PDFファイルを直接分析")
    uploaded_file = st.file_uploader("決算短信のPDFを選択してください", type="pdf")
    if uploaded_file and working_model:
        analyze_pdf(uploaded_file.read(), working_model)
