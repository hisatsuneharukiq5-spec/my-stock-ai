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

# 安定版モデルを指定
MODEL_NAME = "gemini-1.5-flash"

# --- 2. データ取得関数 ---
def get_stock_data(ticker_code):
    """株価・指標・ニュースを取得"""
    ticker_symbol = f"{ticker_code}.T"  # 日本株用に.Tを付与
    stock = yf.Ticker(ticker_symbol)
    
    # 基本情報
    info = stock.info
    # 株価履歴（直近6ヶ月）
    hist = stock.history(period="6mo")
    # ニュース
    news = stock.news
    
    return info, hist, news

# --- 3. AI分析関数 ---
def analyze_with_ai(info, news, pdf_text=None):
    """数字とニュースをまとめてAIが判断"""
    model = genai.GenerativeModel(MODEL_NAME)
    
    prompt = f"""
    あなたは凄腕の証券アナリストです。以下の情報を元に、この企業を分析してください。
    
    【基本データ】
    企業名: {info.get('longName', '不明')}
    現在株価: {info.get('currentPrice', '不明')}円
    PER: {info.get('trailingPE', '不明')}倍 / PBR: {info.get('priceToBook', '不明')}倍
    配当利回り: {info.get('dividendYield', 0) * 100:.2f}%
    
    【最新ニュース】
    {str([n.get('title') for n in news[:5]])}
    
    【追加資料(PDF内容)】
    {pdf_text[:5000] if pdf_text else "なし"}
    
    上記を踏まえ：
    1. この企業の「現在の通信簿（5段階評価）」とその理由
    2. ニュースから読み取れる「世間の期待度や懸念点」
    3. 今後の投資戦略（買い時か、様子見か）
    を、投資初心者にもわかりやすく解説してください。
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. メイン画面 (UI) ---
st.set_page_config(page_title="AI株・掲示板アナライザー", layout="wide")

st.title("📈 AI株価・世論アナライザー")
st.caption("銘柄コードを入れるだけで、数字・ニュース・AI分析を一括表示します")

# 銘柄入力
ticker_input = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker_input:
    try:
        with st.spinner("データを取得中..."):
            info, hist, news = get_stock_data(ticker_input)
            
        # --- レイアウト: 上段 (数字とチャート) ---
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
            st.write(f"**PER:** {info.get('trailingPE', '---')} 倍")
            st.write(f"**PBR:** {info.get('priceToBook', '---')} 倍")
            st.write(f"**利回り:** {info.get('dividendYield', 0) * 100:.2f} %")
            st.write(f"**時価総額:** {info.get('marketCap', 0) // 10**8:,} 億円")
            
        with col2:
            # 株価チャート (Plotlyでプロっぽく)
            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='株価')])
            fig.update_layout(title="直近6ヶ月の株価推移", margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig, use_container_width=True)

        # --- 中段: 世間の声 (簡易掲示板風) ---
        st.subheader("📢 市場の声・関連ニュース")
        if news:
            for n in news[:3]:
                with st.expander(f"📰 {n['title']}"):
                    st.write(f"ソース: {n['publisher']}")
                    st.write(f"[記事を読む]({n['link']})")
        else:
            st.write("現在、目立ったニュースはありません。")

        # --- 下段: AIの総評 ---
        st.subheader("🤖 AIによる総合診断")
        if st.button("AI分析を実行"):
            analysis = analyze_with_ai(info, news)
            st.success("分析が完了しました")
            st.markdown(analysis)

    except Exception as e:
        st.error(f"データの取得に失敗しました。正しいコードか確認してください。 (Error: {e})")

# --- おまけ: PDF深掘り機能 ---
st.divider()
with st.expander("📄 もっと詳しく！決算PDFをアップロードして分析"):
    uploaded_file = st.file_uploader("決算短信などのPDFを選択", type="pdf")
    if uploaded_file and ticker_input:
        if st.button("PDFも含めて再分析"):
            text = ""
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page in doc: text += page.get_text()
            info, _, news = get_stock_data(ticker_input)
            result = analyze_with_ai(info, news, text)
            st.markdown(result)
