import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. 初期設定 (最もエラーが起きにくい書き方に変更) ---
# モデル名を極限までシンプルにしました
MODEL_NAME = "gemini-1.5-flash"

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("SecretsにAPIキーを設定してください。")

# --- 2. データ取得関数 ---
def get_stock_data(ticker_code):
    ticker_symbol = f"{ticker_code}.T"
    stock = yf.Ticker(ticker_symbol)
    
    try:
        info = stock.info
        hist = stock.history(period="6mo")
    except:
        info, hist = {}, pd.DataFrame()
        
    # ニュースが取れない場合も「エラー」にせず、空リストで返す
    news_list = []
    try:
        raw_news = stock.news
        if raw_news:
            for n in raw_news:
                title = n.get('title') or n.get('description', '最新トピック')
                news_list.append({"title": title, "link": n.get('link', '#')})
    except:
        pass
        
    return info, hist, news_list

# --- 3. AI掲示板分析 (ニュースがなくても動く「推論」モード) ---
def analyze_with_ai(info, news, hist):
    try:
        # モデル呼び出しを最も安全な形に変更
        model = genai.GenerativeModel(MODEL_NAME)
        
        # 株価の動き（上がり気味か、下がり気味か）をAIに伝える
        trend = "上昇傾向" if not hist.empty and hist['Close'].iloc[-1] > hist['Close'].iloc[0] else "下落・停滞傾向"
        
        # ニュースの有無でプロンプトを分岐
        news_text = "\n".join([f"・{n['title']}" for n in news[:3]]) if news else "（特になし）"

        prompt = f"""
        あなたは、投資家たちが集まる「爆速株掲示板」のベテラン管理人です。
        以下のデータだけから、ネット上の住民がどんな「噂」や「煽り合い」をしているか、リアルに再現してください。
        
        【銘柄】: {info.get('longName', '不明')} ({info.get('symbol', '---')})
        【株価状況】: 現在値 {info.get('currentPrice', '---')}円 / 直近6ヶ月は「{trend}」
        【指標】: PER {info.get('trailingPE', '---')}倍 / 配当利回り {info.get('dividendYield', 0)*100:.2f}%
        【最新ニュース】: {news_text}
        
        以下の形式で「掲示板の空気感」を教えてください：
        1. 【掲示板の熱量】: 盛り上がってるか、お通夜状態か
        2. 【買い方の声】: 強気な住民の書き込み（例：〇〇だし余裕でホールド！）
        3. 【売り方の声】: 弱気な住民の不安（例：〇〇が怪しい、逃げろ！）
        4. 【管理人の予言】: ネットの熱量から見た「明日の注目ポイント」
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # エラーが出た場合も画面を止めない
        return f"AIが休憩中です（エラー: {str(e)[:50]}...）。少し待ってからボタンを押してください。"

# --- 4. メイン画面 (UI) ---
st.set_page_config(page_title="AI株価・世論アナライザー", layout="wide")
st.title("📈 AI株価・世論アナライザー")

ticker = st.text_input("証券コードを入力 (例: 7203)", max_chars=4)

if ticker:
    with st.spinner("データを読み込み中..."):
        info, hist, news = get_stock_data(ticker)
        
    # --- 上段：数字とチャート ---
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("現在株価", f"{info.get('currentPrice', '---')} 円")
        st.write(f"**PER:** {info.get('trailingPE', '---')} 倍")
        st.write(f"**利回り:** {info.get('dividendYield', 0)*100:.2f} %")
        st.write(f"**時価総額:** {info.get('marketCap', 0)//10**8:,} 億円")
        
    with c2:
        if not hist.empty:
            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], mode='lines', line=dict(color='#00d1b2'))])
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 下段：トピックと掲示板 ---
    left, right = st.columns(2)
    
    with left:
        st.subheader("📢 最新トピック")
        if news:
            for n in news[:3]:
                st.markdown(f"🔗 [{n['title']}]({n['link']})")
        else:
            st.info("Yahooニュース等から直接取得できませんでした。")
            st.write("▼ 外部サイトで直接チェック（おすすめ）")
            st.markdown(f"👉 [Yahoo掲示板で「{ticker}」を見る](https://finance.yahoo.co.jp/quote/{ticker}.T/bbs)")
            st.markdown(f"👉 [みんかぶで「{ticker}」を調べる](https://minkabu.jp/stock/{ticker})")

    with right:
        st.subheader("💬 AI投資家掲示板")
        if st.button("掲示板の声を読み込む"):
            with st.spinner("スレッドを解析中..."):
                analysis_result = analyze_with_ai(info, news, hist)
                st.markdown(analysis_result)
