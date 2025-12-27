import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. 初期設定 ---
# モデル名を「gemini-1.5-flash」に固定（一番安定して動くモデルです）
MODEL_NAME = "gemini-1.5-flash"

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーが設定されていません。")

# --- 2. データ取得関数 ---
def get_stock_data(ticker_code):
    ticker_symbol = f"{ticker_code}.T"
    stock = yf.Ticker(ticker_symbol)
    
    # 株価情報とチャート用履歴
    try:
        info = stock.info
        hist = stock.history(period="6mo")
    except:
        info, hist = {}, pd.DataFrame()
        
    # ニュース取得（ここを一番安全な方法に変更）
    news_list = []
    try:
        raw_news = stock.news
        if raw_news:
            for n in raw_news:
                # 辞書の形をチェックしながら安全にタイトルを拾う
                title = n.get('title') or n.get('description', '最新トピック')
                link = n.get('link', '#')
                news_list.append({"title": title, "link": link})
    except:
        pass # ニュースが取れなくてもエラーにしない
        
    return info, hist, news_list

# --- 3. AI分析関数（掲示板シミュレーター） ---
def analyze_with_ai(info, news):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        # ニュースが空の場合の対策
        news_text = ""
        if news:
            for n in news[:5]:
                news_text += f"・{n['title']}\n"
        else:
            news_text = "（現在、個別の新着ニュースはありません）"

        prompt = f"""
        あなたは投資家が集まるネット掲示板（5ちゃんねるの市況板など）の伝説的な管理人です。
        以下のデータを元に、掲示板の住民たちが今この株について何を話しているか、リアルに再現して要約してください。
        
        【企業名】: {info.get('longName', '不明')} ({info.get('symbol', '---')})
        【現在株価】: {info.get('currentPrice', '---')}円
        【指標】: PER {info.get('trailingPE', '---')}倍 / PBR {info.get('priceToBook', '---')}倍
        【最近の話題】:
        {news_text}
        
        以下の構成で出力してください：
        1. 【掲示板の勢い】: 盛り上がっているか、静かか
        2. 【住民の声（期待）】: 買い方の書き込みを再現
        3. 【住民の声（不安）】: 売り方の書き込みを再現
        4. 【管理人の一言】: 結局、今は「買い」か「待ち」か？
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI分析中にエラーが発生しました。時間を置いて再度お試しください。 (詳細: {e})"

# --- 4. メイン画面 (UI) ---
st.set_page_config(page_title="AI株価・世論アナライザー", layout="wide")
st.title("📈 AI株価・世論アナライザー")

ticker = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker:
    with st.spinner("データを読み込み中..."):
        info, hist, news = get_stock_data(ticker)
        
    # --- 上段：数字とチャート ---
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
        st.write(f"**PER:** {info.get('trailingPE', '---')} 倍")
        st.write(f"**利回り:** {info.get('dividendYield', 0)*100:.2f} %")
        st.write(f"**時価総額:** {info.get('marketCap', 0)//10**8:,} 億円")
        
    with col2:
        if not hist.empty:
            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines', line=dict(color='#00d1b2'))])
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0), title="6ヶ月の株価推移")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 下段：ニュースとAI分析 ---
    left, right = st.columns(2)
    
    with left:
        st.subheader("📢 関連トピック")
        if news:
            for n in news[:3]:
                st.markdown(f"🔗 [{n['title']}]({n['link']})")
        else:
            st.info("ニュースは取得できませんでした。AIが数値から推測します。")

    with right:
        st.subheader("💬 AI投資家掲示板")
        if st.button("掲示板の声を読み込む"):
            with st.spinner("スレッドを解析中..."):
                analysis_result = analyze_with_ai(info, news)
                st.markdown(analysis_result)
