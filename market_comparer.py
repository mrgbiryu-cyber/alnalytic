import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.fetcher import get_ohlcv
from src.calculator import IndicatorCalculator

st.set_page_config(layout="wide", page_title="Market Comparison Lab")

st.title("🧪 2-Market 비교 분석 연구소")
st.markdown("---")

# --- 사이드바 설정 ---
st.sidebar.header("⚙️ 분석 설정")
col_m1, col_m2 = st.sidebar.columns(2)
with col_m1:
    market_a = st.text_input("마켓 A", "KRW-BTC")
    # 한국 시간(KST) 입력을 기본으로 설정
    time_a_str = st.text_input("기준 시간 A (한국시간 KST)", datetime.now().strftime("%Y-%m-%d %H:%M"), key="ta")
with col_m2:
    market_b = st.text_input("마켓 B", "KRW-ETH")
    time_b_str = st.text_input("기준 시간 B (한국시간 KST)", datetime.now().strftime("%Y-%m-%d %H:%M"), key="tb")

interval = st.sidebar.selectbox("기준 분봉 설정", [1, 3, 5, 10, 15, 30, 60], index=1)

with st.sidebar.expander("🛠️ 지표 세부 파라미터"):
    pass1_n = st.slider("PASS1 평균 개수", 1, 50, 3)
    wide_n = st.slider("WideTrend1 (N)", 1, 50, 17)
    wide2_n = st.slider("WideTrend2 (N)", 1, 20, 3)
    trend_n = st.slider("TrendAvg (N)", 1, 10, 2)
    fast_n = st.slider("FastRate 범위", 5, 50, 24)

# --- 분석 실행 ---
if st.sidebar.button("🚀 비교 분석 시작"):
    try:
        # 입력받은 한국 시간(KST)에서 9시간을 빼서 세계 표준시(UTC)로 변환
        trade_time_a = pd.to_datetime(time_a_str) - timedelta(hours=9)
        trade_time_b = pd.to_datetime(time_b_str) - timedelta(hours=9)
    except Exception as e:
        st.error("시간 형식이 잘못되었습니다. YYYY-MM-DD HH:MM 형식으로 입력해주세요.")
        st.stop()

    # 1. 데이터 수집
    with st.spinner("데이터 수집 및 분석 중..."):
        # 과거 데이터 (지표 계산용)
        df_a_past = get_ohlcv(market_a, trade_time_a, interval_min=interval, count=200)
        df_b_past = get_ohlcv(market_b, trade_time_b, interval_min=interval, count=200)
        
        # 1분봉 데이터 (PASS1용)
        df_a_1m = get_ohlcv(market_a, trade_time_a, interval_min=1, count=60)
        df_b_1m = get_ohlcv(market_b, trade_time_b, interval_min=1, count=60)
        
        # 미래 데이터 (1시간 = 60분)
        df_a_future = get_ohlcv(market_a, trade_time_a + timedelta(minutes=60), interval_min=1, count=120)
        df_b_future = get_ohlcv(market_b, trade_time_b + timedelta(minutes=60), interval_min=1, count=120)

    if df_a_past.empty or df_b_past.empty:
        st.error("데이터를 가져오는데 실패했습니다. 마켓명이나 시간을 확인해주세요.")
    else:
        # 2. 지표 계산
        calc = IndicatorCalculator()
        params = {
            'pass1_n': pass1_n, 'wide_n': wide_n, 'wide2_n': wide2_n,
            'trend_n': trend_n, 'fast_n': fast_n
        }
        
        df_a_past.attrs['interval'] = interval
        df_b_past.attrs['interval'] = interval
        
        res_a = calc.calculate(df_a_past, df_a_1m, 0, params=params)
        res_b = calc.calculate(df_b_past, df_b_1m, 0, params=params)

        # 3. 결과 판정 (상위 2% / 하위 2%)
        def judge_outcome(df_future, start_price, trade_time):
            if df_future.empty: return "Unknown", 0
            df_after = df_future[df_future['time'] > trade_time].copy()
            if df_after.empty: return "No Data", 0
            
            max_high = df_after['high'].max()
            min_low = df_after['low'].min()
            
            high_rate = (max_high - start_price) / start_price * 100
            low_rate = (min_low - start_price) / start_price * 100
            
            if high_rate >= 2.0: return "SUCCESS (OK)", high_rate
            if low_rate <= -2.0: return "FAILURE (X)", low_rate
            return "HOLD", high_rate

        buy_price_a = df_a_past.iloc[-1]['close']
        buy_price_b = df_b_past.iloc[-1]['close']
        
        outcome_a, rate_a = judge_outcome(df_a_future, buy_price_a, trade_time_a)
        outcome_b, rate_b = judge_outcome(df_b_future, buy_price_b, trade_time_b)

        # 4. 화면 표시
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"🅰️ {market_a}")
            st.metric("결과", outcome_a, f"{rate_a:.2f}%")
            st.write(f"진입가: {buy_price_a:.8f}") # 소수점 8자리까지 표시 (밈코인 대응)
            
        with col2:
            st.subheader(f"🅱️ {market_b}")
            st.metric("결과", outcome_b, f"{rate_b:.2f}%")
            st.write(f"진입가: {buy_price_b:.8f}")

        st.markdown("---")
        st.subheader("📊 지표 비교 데이터")
        
        def get_val(res, pattern):
            for k, v in res.items():
                if pattern in k: return v
            return 0

        # 지표 이름 매핑 (계산기 내부 키값과 맞춤)
        metrics = {
            "PASS1 Ratio": "PASS1",
            "WideTrend1": "wideTrendAvg (n",
            "WideTrend2": "wideTrendAvg2",
            "TrendAvg": "trendAvg",
            "CrossAvg": "CrossAvg",
            "FastRate": "FastRate",
            "PrevPriceRate(%)": "PrevPriceRate"
        }
        
        comp_data = []
        for display_name, pattern in metrics.items():
            val_a = get_val(res_a, pattern)
            val_b = get_val(res_b, pattern)
            diff = val_a - val_b
            comp_data.append({
                "지표명": display_name,
                f"Market A ({market_a})": val_a,
                f"Market B ({market_b})": val_b,
                "차이 (A-B)": diff
            })
        
        st.table(pd.DataFrame(comp_data).set_index("지표명"))

        # 5. AI 지표 비교 분석 리포트
        st.markdown("---")
        st.subheader("🧐 AI 지표 비교 분석 리포트")
        
        # 마켓명이 같으면 'A 시점', 'B 시점'으로 표시하여 분석 리포트 가독성 높임
        name_a = f"{market_a} (A시점)" if market_a == market_b else market_a
        name_b = f"{market_b} (B시점)" if market_a == market_b else market_b

        analysis = []
        
        # PASS1 분석
        p1_a = get_val(res_a, "PASS1")
        p1_b = get_val(res_b, "PASS1")
        if abs(p1_a - p1_b) > 0.3:
            stronger = name_a if p1_a > p1_b else name_b
            weaker = name_b if p1_a > p1_b else name_a
            analysis.append(f"💡 **거래량 폭발력**: {stronger}의 PASS1 수치가 {weaker}보다 눈에 띄게 높습니다. {stronger}일 때 순간적인 매수 에너지가 훨씬 강하게 들어온 상태입니다.")

        # WideTrend 분석
        w1_a = get_val(res_a, "wideTrendAvg (n")
        w1_b = get_val(res_b, "wideTrendAvg (n")
        if (w1_a >= 1.0 and w1_b < 1.0) or (w1_a < 1.0 and w1_b >= 1.0):
            up_m = name_a if w1_a >= 1.0 else name_b
            down_m = name_b if w1_a >= 1.0 else name_a
            analysis.append(f"💡 **장기 추세(Wide1)**: {up_m}은 장기 추세가 상승세(1.0 이상)인 반면, {down_m}은 하락세입니다. 상승장에서는 {up_m}이 훨씬 유리합니다.")

        # CrossAvg 분석 (이격도)
        c_a = get_val(res_a, "CrossAvg")
        c_b = get_val(res_b, "CrossAvg")
        if abs(c_a - c_b) > 0.005:
            higher = name_a if c_a > c_b else name_b
            analysis.append(f"💡 **이격도(Cross)**: {higher}의 이격도가 더 높습니다. 이는 단기 흐름이 장기 평균보다 위에서 놀고 있다는 뜻이며, 더 강한 돌파 에너지를 의미합니다.")

        # PrevPriceRate 분석
        pr_a = get_val(res_a, "PrevPriceRate")
        pr_b = get_val(res_b, "PrevPriceRate")
        if abs(pr_a - pr_b) > 0.5:
            jump = name_a if pr_a > pr_b else name_b
            analysis.append(f"💡 **직전 급등**: {jump}는 진입 직전에 이미 {max(pr_a, pr_b):.2f}% 상승했습니다. 이미 많이 오른 상태인지 체크가 필요합니다.")

        # 결과에 따른 종합 코멘트
        if (outcome_a.startswith("SUCCESS") and outcome_b.startswith("FAILURE")):
            analysis.append(f"🚨 **결론**: {name_a}는 지표와 추세가 받쳐주어 성공했지만, {name_b}는 위의 지표 결함으로 인해 실패(손절)했을 가능성이 큽니다.")
        elif (outcome_a.startswith("FAILURE") and outcome_b.startswith("SUCCESS")):
            analysis.append(f"🚨 **결론**: {name_b}는 성공했지만, {name_a}는 지표상 불리한 조건이 섞여 있어 실패했습니다.")

        if not analysis:
            st.write("✨ 두 시점의 지표가 매우 유사합니다. 이럴 때는 호가창의 체결 속도나 비트코인의 움직임에 따라 승패가 갈릴 수 있습니다.")
        else:
            for line in analysis:
                st.write(line)

        # AI와 대화하는 인터랙션
        if 'ai_chat_history' not in st.session_state:
            st.session_state.ai_chat_history = []

        def create_context(name, res, outcome, start_p):
            ctx = []
            ctx.append(f"{name} 결과: {outcome}")
            ctx.append(f"PASS1={get_val(res, 'PASS1'):.3f}, Wide1={get_val(res, 'wideTrendAvg (n'):.3f}, CrossAvg={get_val(res, 'CrossAvg'):.3f}")
            ctx.append(f"진입가={start_p:.8f}")
            return "; ".join(ctx)

        def generate_ai_reply(question, ctx):
            return (
                f"질문 감사합니다. {ctx} 데이터를 참고하면, "
                f"현재 가장 눈에 띄는 지표는 PASS1입니다. "
                f"당시 거래량이 평균 대비 {'높았' if 'PASS1' in ctx and float(ctx.split('PASS1=')[1].split(',')[0]) > 1.5 else '낮았'}기 때문에 "
                "현재 질문하신 타점이 어떤 의미인지를 추론할 수 있습니다. "
                "자세한 설명을 원하시면 하단의 지표값과 결과를 말씀해 주세요."
            )

        with st.form("ai_chat_form"):
            user_question = st.text_input("AI에게 질문하기", placeholder="예: 이 타점이 고점인가요?", key="ai_question")
            submitted = st.form_submit_button("질문 보내기")
            if submitted and user_question.strip():
                context_a = create_context(name_a, res_a, outcome_a, buy_price_a)
                context_b = create_context(name_b, res_b, outcome_b, buy_price_b)
                reply = generate_ai_reply(user_question, context_a + " | " + context_b)
                st.session_state.ai_chat_history.append({"question": user_question, "answer": reply})

        if st.session_state.ai_chat_history:
            st.markdown("#### 🗣️ AI와의 대화 기록")
            for entry in st.session_state.ai_chat_history[-4:]:
                st.markdown(f"> **Q:** {entry['question']}")
                st.markdown(f"> **A:** {entry['answer']}")
        
        # 6. 차트 비교
        st.markdown("---")
        st.subheader("📈 차트 흐름 비교 (진입 시점 기준)")
        st.info("💡 **차트가 안 보인다면?** 기준 시간을 '현재'로 설정하셨을 수 있습니다. 미래 데이터(진입 후 1시간)가 아직 생성되지 않은 경우 'No Data'로 표시되며 차트가 비어 보일 수 있으니, 최소 1시간 전의 과거 시간을 입력해 보세요.")
        
        def draw_mini_chart(df, title, trade_time, start_price):
            # 차트 표시를 위해 UTC 데이터를 다시 KST(+9)로 변환
            df_kst = df.copy()
            df_kst['time_kst'] = df_kst['time'] + timedelta(hours=9)
            trade_time_kst = trade_time + timedelta(hours=9)

            # 기준 시점 전후 데이터 필터링 (KST 기준)
            df_v = df_kst[(df_kst['time_kst'] >= trade_time_kst - timedelta(minutes=30)) & 
                          (df_kst['time_kst'] <= trade_time_kst + timedelta(minutes=60))].copy()
            
            if df_v.empty: 
                fig = go.Figure()
                fig.update_layout(title=f"{title} (데이터 없음)", xaxis={"visible": False}, yaxis={"visible": False})
                return fig
            
            # [개선] 저유동성 종목 대응: Y축 범위를 데이터에 더 타이트하게 맞춰서 캔들이 잘 보이게 함
            y_min = min(df_v['low'].min(), start_price * 0.995)
            y_max = max(df_v['high'].max(), start_price * 1.005)

            fig = go.Figure()
            # 캔들스틱 추가
            fig.add_trace(go.Candlestick(
                x=df_v['time_kst'],
                open=df_v['open'], high=df_v['high'], low=df_v['low'], close=df_v['close'],
                name='Price',
                increasing_line_color='#ef5350',  # 한국식 빨강
                decreasing_line_color='#26a69a'   # 한국식 파랑
            ))
            
            # 진입점 표시 (별 모양)
            fig.add_trace(go.Scatter(
                x=[trade_time_kst], y=[start_price],
                mode='markers',
                marker=dict(color='yellow', size=15, symbol='star', line=dict(width=1, color='black')),
                name='Entry'
            ))
            
            # 2% 수익/손실 라인
            if start_price > 0:
                fig.add_hline(y=start_price * 1.02, line_dash="dash", line_color="#ef5350", annotation_text="+2%", line_width=1)
                fig.add_hline(y=start_price * 0.98, line_dash="dash", line_color="#26a69a", annotation_text="-2%", line_width=1)
            
            fig.update_layout(
                title=title,
                xaxis_rangeslider_visible=False,
                height=500,
                yaxis=dict(
                    tickformat=".8f",
                    range=[y_min, y_max],  # [핵심] Y축 범위를 강제로 최적화
                    fixedrange=False
                ),
                margin=dict(l=50, r=50, t=50, b=50)
            )
            return fig

        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            st.plotly_chart(draw_mini_chart(df_a_future, f"{market_a} 흐름", trade_time_a, buy_price_a), use_container_width=True, key="chart_a")
        with c_chart2:
            st.plotly_chart(draw_mini_chart(df_b_future, f"{market_b} 흐름", trade_time_b, buy_price_b), use_container_width=True, key="chart_b")

else:
    st.info("왼쪽 사이드바에서 마켓과 시간을 설정한 후 [비교 분석 시작]을 눌러주세요.")

