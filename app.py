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
    
    # 基本情報
    try:
        info = stock.info
    except:
        info = {}
        
    # 株価推移
    hist = stock.history(period="6mo")
    
    # ニュース（空っぽでもエラーにしない）
    try:
        news = stock.news
        if not news:
            news = []
    except:
        news = []
        
    return info, hist, news

# --- 3. AI分析関数 ---
def analyze_with_ai(info, news, pdf_text=None):
    model = genai.GenerativeModel(MODEL_NAME)
    
    # ニュースがあればタイトルを使い、なければ「最近の傾向」をAIに聞く
    if news:
        news_summary = "\n".join([f"・{n.get('title', '無題')}" for n in news[:5]])
    else:
        news_summary = "現在、取得できる最新ニュースはありません。"
    
    prompt = f"""
    あなたは凄腕の投資家で、人気投資掲示板の管理人です。
    
    【対象企業】: {info.get('longName', '銘柄名不明')} ({info.get('symbol', '---')})
    【現在の株価】: {info.get('currentPrice', '---')}円
    【最新ニュース】:
    {news_summary}
    
    【追加情報(PDF)】:
    {pdf_text[:5000] if pdf_text else "なし"}
    
    上記の情報（ニュースがなければ株価やPDF情報）から、
    この株について「掲示板の住民たちが語りそうな内容」を以下の構成で出力してください。
    
    1. 掲示板でのポジティブな意見（期待されていること）
    2. 掲示板でのネガティブな意見（不安視されていること）
    3. 管理人（あなた）による「結局、今は買いなのか？」の結論
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. メイン画面 (UI) ---
st.set_page_config(page_title="AI株・掲示板アナライザー", layout="wide")
st.title("📈 AI株価・世論アナライザー")

# 銘柄入力
ticker_input = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker_input:
    try:
        info, hist, news = get_stock_data(ticker_input)
        
        # 数値とチャート表示
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
            st.write(f"**PER:** {info.get('trailingPE', '---')} 倍")
            st.write(f"**利回り:** {info.get('dividendYield', 0) * 100:.2f} %")
            
        with col2:
            if not hist.empty:
                fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines')])
                fig.update_layout(title="株価推移", height=250, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig, use_container_width=True)

        # ニュースセクション
        st.subheader("📢 関連ニュース")
        if news:
            for n in news[:3]:
                st.write(f"🔗 [{n.get('title')}]({n.get('link')}) ({n.get('publisher')})")
        else:
            st.info("Yahoo Financeからニュースを取得できませんでした。AIが株価データのみで推測します。")

        # --- AI掲示板セクション ---
        st.divider()
        st.subheader("💬 AI投資家掲示板（世論分析）")
        
        # 分析実行ボタン
        if st.button("掲示板を読み込む"):
            with st.spinner("掲示板の書き込みを集計中..."):
                analysis_result = analyze_with_ai(info, news)
                st.markdown(analysis_result)

    except Exception as e:
        st.error("データの読み込みに失敗しました。証券コードが正しいか確認してください。")

# PDF分析（サイドバー）
with st.sidebar:
    st.header("📄 PDF詳細分析")
    uploaded_file = st.file_uploader("決算短信PDF", type="pdf")
    if uploaded_file and ticker_input:
        if st.button("PDF込みで分析開始"):
            text = ""
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page in doc: text += page.get_text()
            res = analyze_with_ai(info, news, text)
            st.write(res)
