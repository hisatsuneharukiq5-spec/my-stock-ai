import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import fitz  # PyMuPDF

# --- 1. 初期設定 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーをSecretsに設定してください。")

MODEL_NAME = "gemini-1.5-flash"

# --- 2. データ取得関数 ---
def get_stock_data(ticker_code):
    ticker_symbol = f"{ticker_code}.T"
    stock = yf.Ticker(ticker_symbol)
    
    # 基本情報と株価チャート用データ
    try:
        info = stock.info
        hist = stock.history(period="6mo")
    except:
        info, hist = {}, pd.DataFrame()
        
    # ニュース取得 (ここを大幅に強化)
    news_list = []
    try:
        raw_news = stock.news
        if raw_news:
            for n in raw_news:
                title = n.get('title') or n.get('description') or "最新のトピック"
                news_list.append({"title": title, "link": n.get('link', '#')})
    except:
        pass
        
    return info, hist, news_list

# --- 3. AI分析関数 ---
def analyze_with_ai(info, news, pdf_text=None):
    model = genai.GenerativeModel(MODEL_NAME)
    
    news_text = "\n".join([f"・{n['title']}" for n in news]) if news else "直近のニュースなし"
    
    prompt = f"""
    あなたは投資家が集まるネット掲示板の伝説的な「管理人」です。
    以下のデータを見て、掲示板で今どんな議論が起きているか、ユーモアを交えて要約してください。
    
    【企業名】: {info.get('longName', '不明')}
    【指標】: PER {info.get('trailingPE', '---')}倍 / 配当利回り {info.get('dividendYield', 0)*100:.2f}%
    【最新ニュース】: {news_text}
    
    【追加情報(PDF)】: {pdf_text[:4000] if pdf_text else "なし"}
    
    分析指示：
    1. 【掲示板の雰囲気】: 「買い」「売り」どちらの書き込みが多いか？
    2. 【ポジティブ要素】: 住民が期待しているポイント。
    3. 【ネガティブ要素】: 住民がビビっているポイント。
    4. 【管理人の一言】: 結局、今この株はどう見えるか？
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. メイン画面 ---
st.set_page_config(page_title="AI株価・世論アナライザー", layout="wide")
st.title("📈 AI株価・世論アナライザー")

ticker = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker:
    with st.spinner("データを読み込み中..."):
        info, hist, news = get_stock_data(ticker)
        
    # 上段：数字とチャート
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
        st.write(f"**PER:** {info.get('trailingPE', '---')} 倍")
        st.write(f"**利回り:** {info.get('dividendYield', 0)*100:.2f} %")
    with c2:
        if not hist.empty:
            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines', line=dict(color='#1f77b4'))])
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # 下段：ニュースとAI掲示板
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("📢 最新ニュース")
        if news:
            for n in news[:3]:
                st.write(f"🔹 [{n['title']}]({n['link']})")
        else:
            st.info("ニュースが見つかりませんでした。AIが数値から分析します。")

    with col_b:
        st.subheader("💬 AI投資家掲示板")
        if st.button("掲示板の声を聴く"):
            with st.spinner("書き込みを集計中..."):
                res = analyze_with_ai(info, news)
                st.markdown(res)

# 決算PDF分析（サイドバー）
with st.sidebar:
    st.header("📄 PDF詳細分析")
    up_file = st.file_uploader("PDFを投入", type="pdf")
    if up_file and ticker:
        if st.button("PDFを読んで掲示板へ流す"):
            doc_text = ""
            with fitz.open(stream=up_file.read(), filetype="pdf") as d:
                for p in d: doc_text += p.get_text()
            res = analyze_with_ai(info, news, doc_text)
            st.write(res)
