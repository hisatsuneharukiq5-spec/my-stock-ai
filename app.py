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

# 安定して動く1.5モデルを使用
MODEL_NAME = "gemini-1.5-flash"

# --- 2. データ取得関数 ---
def get_stock_data(ticker_code):
    ticker_symbol = f"{ticker_code}.T"
    stock = yf.Ticker(ticker_symbol)
    
    info = stock.info
    hist = stock.history(period="6mo")
    
    # ニュース取得（エラーが出ないように安全に取得）
    try:
        raw_news = stock.news
        news = []
        if raw_news:
            for n in raw_news:
                # 'title' がない場合でもエラーにならないように .get() を使う
                news.append({
                    "title": n.get("title", "ニュースタイトルなし"),
                    "link": n.get("link", "#"),
                    "publisher": n.get("publisher", "不明なソース")
                })
    except:
        news = []
    
    return info, hist, news

# --- 3. AI分析関数 ---
def analyze_with_ai(info, news, pdf_text=None):
    model = genai.GenerativeModel(MODEL_NAME)
    
    news_summary = "\n".join([f"・{n['title']}" for n in news[:5]])
    
    prompt = f"""
    あなたはプロの投資アドバイザー兼、有名投資掲示板の管理人です。
    以下の情報を元に、この企業を分析して、投資家たちが今どんな雰囲気（世論）なのか教えてください。
    
    【企業名】: {info.get('longName', '不明')}
    【指標】: PER {info.get('trailingPE', '---')}倍 / PBR {info.get('priceToBook', '---')}倍
    【最新ニュース】:
    {news_summary}
    
    【PDF追加情報】:
    {pdf_text[:5000] if pdf_text else "なし"}
    
    分析項目：
    1. 現在の業績と株価の評価（「買い」「待ち」など）
    2. 掲示板で話題になりそうな「世間の噂・期待・不安」
    3. ズバリ、今後の注目ポイントは？
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. メイン画面 (UI) ---
st.set_page_config(page_title="AI株・掲示板アナライザー", layout="wide")
st.title("📈 AI株価・世論アナライザー")

ticker_input = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker_input:
    try:
        with st.spinner("データを取得中..."):
            info, hist, news = get_stock_data(ticker_input)
            
        # 上段：数字とチャート
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
            st.write(f"**PER:** {info.get('trailingPE', '---')} 倍")
            st.write(f"**PBR:** {info.get('priceToBook', '---')} 倍")
            st.write(f"**利回り:** {info.get('dividendYield', 0) * 100:.2f} %")
            st.write(f"**時価総額:** {info.get('marketCap', 0) // 10**8:,} 億円")
            
        with col2:
            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='株価')])
            fig.update_layout(title="直近6ヶ月の株価推移", height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)

        # 中段：市場の声（ニュース）
        st.subheader("📢 市場の声・関連ニュース")
        if news:
            for n in news[:3]:
                with st.expander(f"📰 {n['title']}"):
                    st.write(f"ソース: {n['publisher']}")
                    st.write(f"[記事を読む]({n['link']})")
        else:
            st.write("現在、目立ったニュースはありません。")

        # 下段：AI分析ボタン
        st.divider()
        if st.button("🤖 AI掲示板・総合診断を実行"):
            with st.spinner("AIが市場の空気を読み取っています..."):
                analysis = analyze_with_ai(info, news)
                st.success("分析が完了しました！")
                st.markdown(analysis)

    except Exception as e:
        st.error(f"データの表示中にエラーが発生しました。時間を置いてから再度お試しください。")

# PDFアップロード機能（サイドバー）
with st.sidebar:
    st.header("📄 PDF深掘り分析")
    uploaded_file = st.file_uploader("決算PDFをアップロード", type="pdf")
    if uploaded_file and ticker_input:
        if st.button("PDFも含めて分析"):
            text = ""
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page in doc: text += page.get_text()
            info, _, news = get_stock_data(ticker_input)
            result = analyze_with_ai(info, news, text)
            st.write(result)
