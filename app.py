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
    
    info = stock.info
    hist = stock.history(period="6mo")
    # ニュース取得のエラー対策
    try:
        news = stock.news
        if not news: news = []
    except:
        news = []
    
    return info, hist, news

# --- 3. AI分析関数 ---
def analyze_with_ai(info, news, pdf_text=None):
    model = genai.GenerativeModel(MODEL_NAME)
    
    # ニュースタイトルの抽出（エラー回避版）
    news_titles = [n.get('title', '無題のニュース') for n in news[:5]]
    
    prompt = f"""
    あなたはプロの投資アドバイザーです。以下の情報を分析してください。
    
    【企業情報】
    企業名: {info.get('longName', '不明')}
    株価: {info.get('currentPrice', '不明')}円
    PER: {info.get('trailingPE', '不明')} / PBR: {info.get('priceToBook', '不明')}
    
    【市場のニュース・話題】
    {news_titles}
    
    【PDF資料】
    {pdf_text[:5000] if pdf_text else "なし"}
    
    上記を元に、以下の3点を「投資家掲示板」で話題になりそうな口調も交えて解説してください。
    1. 現在の業績は「買い」か？
    2. ニュースから見える「世間のポジティブな噂・ネガティブな懸念」
    3. ズバリ、今後の注目ポイント
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. メイン画面 ---
st.set_page_config(page_title="AI株・掲示板アナライザー", layout="wide")
st.title("📈 AI株価・世論アナライザー")

ticker_input = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker_input:
    try:
        with st.spinner("データを取得中..."):
            info, hist, news = get_stock_data(ticker_input)
            
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
            st.write(f"**PER:** {info.get('trailingPE', '---')} 倍")
            st.write(f"**PBR:** {info.get('priceToBook', '---')} 倍")
            st.write(f"**利回り:** {info.get('dividendYield', 0) * 100:.2f} %")
            
        with col2:
            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='株価')])
            fig.update_layout(title="直近6ヶ月の株価推移", height=300, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig, use_container_width=True)

        # --- 修正ポイント: ニュース・掲示板セクション ---
        st.subheader("📢 市場の声 (最新ニュース)")
        if news:
            for n in news[:3]:
                # .get('title') を使うことでエラーを回避
                title = n.get('title', '詳細情報なし')
                publisher = n.get('publisher', '不明なソース')
                link = n.get('link', '#')
                with st.expander(f"📌 {title}"):
                    st.write(f"ソース: {publisher}")
                    st.write(f"[記事をチェックする]({link})")
        else:
            st.warning("現在、取得できる新しいニュースはありません。")

        st.divider()

        # --- AIの総評 ---
        if st.button("🤖 AI掲示板・総合診断を実行"):
            with st.spinner("AIが市場の空気を読んでいます..."):
                analysis = analyze_with_ai(info, news)
                st.success("分析完了！")
                st.markdown(analysis)

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")

# PDFアップロード機能（下部に配置）
with st.sidebar:
    st.header("📄 決算PDF分析")
    uploaded_file = st.file_uploader("PDFを追加して深掘り", type="pdf")
    if uploaded_file and ticker_input:
        if st.button("PDF込みで分析"):
            text = ""
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page in doc: text += page.get_text()
            info, _, news = get_stock_data(ticker_input)
            result = analyze_with_ai(info, news, text)
            st.write(result)
