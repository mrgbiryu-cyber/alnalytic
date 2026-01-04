import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import glob
import io  # 엑셀 변환을 위한 모듈
from datetime import datetime
from src.parser import load_all_data

st.set_page_config(layout="wide", page_title="부자의 트레이딩 분석기 (Expi)")

st.title("🧪 테스트(Expi Mode)")
st.markdown("---")

DATA_DIR = "data"
# 색상 매핑 (더 선명하게 변경)
COLOR_MAP = {"ok": "#00FF00", "x": "#FF0000", "NB": "#0000FF", "unknown": "gray"}

# --- 세션 초기화 ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'is_analyzed' not in st.session_state:
    st.session_state.is_analyzed = False

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 다양한 로그 확장자 대응 (.txt, .txt.log, .log)
files = glob.glob(os.path.join(DATA_DIR, "acc_log.*"))
dates = set()
for f in files:
    basename = os.path.basename(f)
    # acc_log.YYYY-MM-DD... 형태에서 날짜만 추출
    import re
    match = re.search(r'acc_log\.(\d{4}-\d{2}-\d{2})', basename)
    if match:
        dates.add(match.group(1))
available_dates = sorted(list(dates), reverse=True)

st.sidebar.header("📅 데이터 로드")
seed_money = st.sidebar.number_input("시작 자산 (KRW)", value=162982, step=1000)
if not available_dates:
    st.sidebar.error(f"'{DATA_DIR}' 폴더에 로그 파일이 없습니다.")
else:
    mode = st.sidebar.radio("분석 모드", ["단일 날짜", "기간 종합"])
    
    if mode == "단일 날짜":
        s_date = st.sidebar.selectbox("날짜", available_dates)
        selected_dates = [s_date]
    else:
        selected_dates = st.sidebar.multiselect("날짜", available_dates, default=available_dates)

    if st.sidebar.button("🚀 분석 시작"):
        with st.spinner('로그 분석 중...'):
            raw_df = load_all_data(DATA_DIR, selected_dates)
            st.session_state.df = raw_df
            st.session_state.is_analyzed = True

# --- 메인 화면 ---
if st.session_state.is_analyzed and not st.session_state.df.empty:
    df = st.session_state.df

    # --- 사이드바 필터 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔎 결과 필터")
    
    all_results = sorted(df['result'].unique())
    res_filter = st.sidebar.multiselect(
        "보고 싶은 결과 선택", 
        all_results, 
        default=all_results
    )
    
    filtered_df = df[df['result'].isin(res_filter)]

    # --- [NEW] 엑셀 다운로드 버튼 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 데이터 내보내기")
    
    if not filtered_df.empty:
        # 엑셀 바이너리 생성
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Analysis_Data')
            
        st.sidebar.download_button(
            label="📥 엑셀파일(.xlsx) 다운로드",
            data=buffer,
            file_name=f"expi_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.ms-excel",
            help="현재 필터링된 데이터를 엑셀로 내려받습니다."
        )

    # 요약 지표
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    ok_cnt = len(filtered_df[filtered_df['result']=='ok'])
    x_cnt = len(filtered_df[filtered_df['result']=='x'])
    total_cnt = len(filtered_df)
    win_rate = (ok_cnt / (ok_cnt + x_cnt) * 100) if (ok_cnt + x_cnt) > 0 else 0
    avg_profit = filtered_df['profit_rate'].mean() if 'profit_rate' in filtered_df.columns else 0
    
    # 복리 및 실제 수익률 계산
    total_profit_krw = filtered_df['profit_krw'].sum() if 'profit_krw' in filtered_df.columns else 0
    actual_return = (total_profit_krw / seed_money * 100) if seed_money > 0 else 0
    
    c1.metric("Total", total_cnt)
    c2.metric("OK", ok_cnt)
    c3.metric("X", x_cnt)
    c4.metric("Win Rate", f"{win_rate:.1f}%")
    c5.metric("Profit (KRW)", f"{total_profit_krw:,.0f}₩")
    c6.metric("Actual Return", f"{actual_return:.2f}%")
    st.markdown("---")

    # 탭 구성
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 지표 분포", 
        "🕸️ 패턴 찾기", 
        "🔍 상관관계", 
        "📋 원본 데이터", 
        "🧪 시뮬레이션 (A/B)", 
        "🤖 AI 파라미터 최적화" 
    ])

    numeric_cols = [
        'profit_rate', 'PASS1_Ratio', 'BID5_Ratio', 
        'wideTrendAvg', 'wideTrendAvg2', 'crossAvg', 
        'trendAvg', 'val', 'upRate', 'fastRate'
    ]
    target_cols = [c for c in numeric_cols if c in filtered_df.columns]

    # [Tab 1] 지표 분포
    with tab1:
        st.markdown("##### 📊 전체 지표별 분포")
        
        for sel_col in target_cols:
            st.markdown(f"**🔍 {sel_col}**")
            c_h, c_b = st.columns(2)
            with c_h:
                fig_h = px.histogram(filtered_df, x=sel_col, color="result", 
                                     barmode="overlay", color_discrete_map=COLOR_MAP, 
                                     opacity=0.6, title=f"{sel_col} 분포도")
                fig_h.update_layout(font=dict(size=12), height=350)
                st.plotly_chart(fig_h, use_container_width=True)
            with c_b:
                fig_b = px.box(filtered_df, x="result", y=sel_col, color="result", 
                               color_discrete_map=COLOR_MAP, title=f"{sel_col} 범위 박스")
                fig_b.update_layout(font=dict(size=12), height=350)
                st.plotly_chart(fig_b, use_container_width=True)
            st.markdown("---")

    # [Tab 2] Parallel Coordinates (수정됨: 아웃라이어 제거 옵션 추가)
    with tab2:
        st.markdown("##### 🕸️ 성공/실패 패턴 투시경")
        
        # [기능 추가] 아웃라이어 제거 옵션
        with st.expander("🛠️ 그래프가 찌그러져 보이면 여길 눌러서 '상한값 제한'을 조절하세요", expanded=True):
            st.info("값이 너무 큰 데이터(Outlier)가 하나라도 있으면 그래프 눈금이 깨집니다. 아래 슬라이더로 상위 몇 %를 자를지 정하세요.")
            quantile_limit = st.slider("데이터 포함 범위 (예: 0.95는 상위 5% 제거)", 0.8, 1.0, 0.98, 0.01)

        selected_pc_cols = st.multiselect("분석할 지표 (순서 변경 가능)", target_cols, default=target_cols)
        
        if len(filtered_df) > 0 and len(selected_pc_cols) > 1:
            p_df = filtered_df.copy()
            
            # [핵심] 아웃라이어 필터링 (그래프 왜곡 방지)
            for col in selected_pc_cols:
                limit_val = p_df[col].quantile(quantile_limit)
                p_df = p_df[p_df[col] <= limit_val]
            
            p_df['color_val'] = p_df['result'].map({'ok':1, 'x':0}).fillna(0.5)
            
            fig_p = px.parallel_coordinates(
                p_df, 
                dimensions=selected_pc_cols,
                color="color_val", 
                range_color=[0,1], 
                color_continuous_scale=[(0,"#FF0000"), (0.5,"lightgray"), (1,"#00FF00")]
            )
            
            # [핵심] 레이아웃 조정: 글자 크기 키우기 & 마진 확보
            fig_p.update_layout(
                height=600,
                font=dict(size=16, color="black", family="Arial Black"), # 폰트 키움
                margin=dict(l=60, r=60, t=60, b=40) # 좌우 여백 확보
            )
            st.plotly_chart(fig_p, use_container_width=True)
            st.caption(f"ℹ️ 상위 {(1-quantile_limit)*100:.1f}% 데이터를 제외하고 보여줍니다. (총 {len(p_df)}건 표시)")
            
        else:
            st.warning("데이터가 부족하거나 지표를 선택해야 합니다.")

    # [Tab 3] Scatter
    with tab3:
        st.markdown("##### 🔍 상관관계")
        c_x, c_y = st.columns(2)
        with c_x:
            def_x = target_cols.index('wideTrendAvg') if 'wideTrendAvg' in target_cols else 0
            x_axis = st.selectbox("X축", target_cols, index=def_x, key="sx")
        with c_y:
            def_y = target_cols.index('trendAvg') if 'trendAvg' in target_cols else 0
            y_axis = st.selectbox("Y축", target_cols, index=def_y, key="sy")
            
        fig_s = px.scatter(
            filtered_df, 
            x=x_axis, y=y_axis, 
            color="result",
            color_discrete_map=COLOR_MAP,
            hover_data=['market', 'timestamp', 'profit_rate', 'bid_price_unit', 'ask_price'],
            title=f"{x_axis} vs {y_axis}"
        )
        # 글자 크기 키우기
        fig_s.update_layout(font=dict(size=14))
        st.plotly_chart(fig_s, use_container_width=True)

    # [Tab 4] Grid
    with tab4:
        st.dataframe(filtered_df.sort_values(['date', 'timestamp'], ascending=False), width="stretch")

    # [Tab 5] 🧪 A/B 테스트 (Dual Simulation) & 전체 검증
    with tab5:
        st.markdown("### ⚖️ A/B 타임프레임 & 지표 비교")
        st.info("좌측(Case A) 설정을 기준으로 전체 매매 내역을 재계산합니다. (PASS1 오류 수정됨)")

        if 'ab_result' not in st.session_state:
            st.session_state.ab_result = None
        if 'batch_result' not in st.session_state:
            st.session_state.batch_result = pd.DataFrame()

        # --- [A/B 설정 폼] ---
        with st.form("ab_test_form"):
            st.markdown("#### 1. 분석 대상 거래 (단건 상세 분석용)")
            selected_idx = st.selectbox(
                "거래 선택", 
                filtered_df.index, 
                format_func=lambda x: f"[{filtered_df.loc[x]['timestamp']}] {filtered_df.loc[x]['market']} ({filtered_df.loc[x]['result']})"
            )
            st.markdown("---")
            
            col_a, col_b = st.columns(2)
            
            # --- [Case A 설정] ---
            with col_a:
                st.markdown("### 🅰️ Case A (전체 적용 기준)")
                tf_a = st.selectbox("분봉 선택 (A)", [1, 3, 5, 10, 15, 30, 60], index=1, key="tf_a") 
                
                with st.expander("🛠️ Case A 지표 상세 설정"):
                    pass1_n_a = st.slider("PASS1 평균개수", 1, 50, 3, key="p1_a")
                    wide_n_a = st.slider("WideTrend1 (N vs N)", 1, 50, 17, key="w_a")
                    wide2_n_a = st.slider("WideTrend2 (N vs N)", 1, 20, 3, key="w2_a")
                    trend_n_a = st.slider("TrendAvg (N vs N)", 1, 10, 2, key="t_a")
                    fast_n_a = st.slider("FastRate 범위", 5, 50, 24, key="f_a")

            # --- [Case B 설정] ---
            with col_b:
                st.markdown("### 🅱️ Case B (비교용)")
                tf_b = st.selectbox("분봉 선택 (B)", [1, 3, 5, 10, 15, 30, 60], index=2, key="tf_b") 
                
                with st.expander("🛠️ Case B 지표 상세 설정"):
                    pass1_n_b = st.slider("PASS1 평균개수", 1, 50, 3, key="p1_b")
                    wide_n_b = st.slider("WideTrend1 (N vs N)", 1, 50, 10, key="w_b")
                    wide2_n_b = st.slider("WideTrend2 (N vs N)", 1, 20, 2, key="w2_b")
                    trend_n_b = st.slider("TrendAvg (N vs N)", 1, 10, 1, key="t_b")
                    fast_n_b = st.slider("FastRate 범위", 5, 50, 14, key="f_b")

            c_btn1, c_btn2 = st.columns([1, 2])
            with c_btn1:
                submit_ab = st.form_submit_button("🚀 선택 거래 상세 분석")
            with c_btn2:
                submit_batch = st.form_submit_button("📊 Case A 설정으로 전체 내역 재계산 (PASS1 복구)")

        # --- [실행 로직] ---
        # 1. 전체 재계산 로직
        if submit_batch:
            with st.spinner(f"총 {len(filtered_df)}건에 대해 PASS1 및 전체 지표 재계산 중..."):
                from src.fetcher import get_ohlcv
                from src.calculator import IndicatorCalculator
                import time
                
                calc = IndicatorCalculator()
                results = []
                params_a = {'pass1_n': pass1_n_a, 'wide_n': wide_n_a, 'wide2_n': wide2_n_a, 'trend_n': trend_n_a, 'fast_n': fast_n_a}
                
                progress_bar = st.progress(0)
                total_rows = len(filtered_df)
                
                # 지표 추출용 헬퍼 함수 (강력한 패턴 매칭)
                def get_val(res_dict, pattern):
                    for k, v in res_dict.items():
                        if pattern in k: return v
                    return 0

                for i, (idx, row) in enumerate(filtered_df.iterrows()):
                    try:
                        market = row['market']
                        trade_time_utc = pd.to_datetime(row['timestamp'])
                        
                        # 1분봉 데이터 수집 (PASS1 계산용) - trade_time_utc까지만 정확히 수집
                        df_1m = get_ohlcv(market, trade_time_utc, interval_min=1, count=60)
                        # 기준 분봉 데이터 수집
                        df_target = get_ohlcv(market, trade_time_utc, interval_min=tf_a, count=200)
                        
                        if df_1m.empty or df_target.empty: continue

                        df_target.attrs['interval'] = tf_a
                        
                        res = calc.calculate(df_target, df_1m, row.get('bid5_24h', 0), params=params_a)
                        
                        if res:
                            res_row = {
                                'timestamp': row['timestamp'],
                                'market': market,
                                'result': row['result'],
                                'Sim_PASS1': get_val(res, "PASS1"),
                                'Sim_Wide1': get_val(res, "wideTrendAvg (n"),
                                'Sim_Wide2': get_val(res, "wideTrendAvg2"),
                                'Sim_Trend': get_val(res, "trendAvg"),
                                'Sim_Cross': get_val(res, "CrossAvg"),
                                'Sim_Fast': get_val(res, "FastRate"),
                                'Sim_PrevRate': get_val(res, "PrevPriceRate")
                            }
                            results.append(res_row)
                        
                    except Exception as e:
                        print(f"Error processing {idx}: {e}")
                    
                    progress_bar.progress((i + 1) / total_rows)
                    time.sleep(0.01)
                
                st.session_state.batch_result = pd.DataFrame(results)
                st.success("✅ 재계산 완료! Sim_PASS1 값이 정상적으로 나와야 합니다.")

        # --- [전체 결과 표시] ---
        if not st.session_state.batch_result.empty:
            st.markdown(f"##### 📋 전체 재계산 결과 (Case A: {tf_a}분봉)")
            
            disp_df = st.session_state.batch_result.copy()
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                disp_df.to_excel(writer, index=False, sheet_name='Sim_Result')
            
            st.download_button(
                label="📥 엑셀 다운로드 (PASS1 수정됨)",
                data=buffer,
                file_name=f"sim_result_fixed_{datetime.now().strftime('%H%M')}.xlsx",
                mime="application/vnd.ms-excel",
                key="tab5_batch_download"
            )

            st.dataframe(
                disp_df.style.format("{:.4f}", subset=[c for c in ['Sim_PASS1', 'Sim_Wide1', 'Sim_Trend', 'Sim_PrevRate'] if c in disp_df.columns]),
                width="stretch"
            )

        # --- [단건 실행 로직] ---
        if submit_ab:
            target_row = filtered_df.loc[selected_idx]
            market = target_row['market']
            trade_time_utc = pd.to_datetime(target_row['timestamp'])
            
            # 미래 데이터 흐름 확보를 위해 fetch_end_time 설정 (차트용)
            fetch_end_time = trade_time_utc + pd.Timedelta(minutes=180)
            
            with st.spinner(f"{market} 분석 중..."):
                from src.fetcher import get_ohlcv
                from src.calculator import IndicatorCalculator
                
                # 차트용 넉넉한 데이터
                df_1m_full = get_ohlcv(market, fetch_end_time, interval_min=1, count=200)
                df_a_full = get_ohlcv(market, fetch_end_time, interval_min=tf_a, count=400)
                df_b_full = get_ohlcv(market, fetch_end_time, interval_min=tf_b, count=400)
                
                if not df_a_full.empty and not df_b_full.empty:
                    calc = IndicatorCalculator()
                    
                    # 지표 계산용 데이터 분리 (매수 시점까지만)
                    # PASS1의 정확도를 위해 1분봉은 trade_time_utc까지만 잘라서 보냅니다.
                    df_1m_calc = df_1m_full[df_1m_full['time'] <= trade_time_utc].copy()
                    df_a_calc = df_a_full[df_a_full['time'] <= trade_time_utc].copy()
                    df_b_calc = df_b_full[df_b_full['time'] <= trade_time_utc].copy()

                    df_a_full.attrs['interval'] = tf_a
                    df_b_full.attrs['interval'] = tf_b
                    
                    params_a = {'pass1_n': pass1_n_a, 'wide_n': wide_n_a, 'wide2_n': wide2_n_a, 'trend_n': trend_n_a, 'fast_n': fast_n_a}
                    params_b = {'pass1_n': pass1_n_b, 'wide_n': wide_n_b, 'wide2_n': wide2_n_b, 'trend_n': trend_n_b, 'fast_n': fast_n_b}
                    
                    res_a = calc.calculate(df_a_calc, df_1m_calc, target_row.get('bid5_24h', 0), params=params_a)
                    res_b = calc.calculate(df_b_calc, df_1m_calc, target_row.get('bid5_24h', 0), params=params_b)
                    
                    st.session_state.ab_result = {
                        'row': target_row,
                        'trade_time_utc': trade_time_utc,
                        'df_a': df_a_full, 'res_a': res_a, 'conf_a': f"{tf_a}분",
                        'df_b': df_b_full, 'res_b': res_b, 'conf_b': f"{tf_b}분",
                    }
                else: st.error("데이터 수집 실패")

        if st.session_state.ab_result:
            res = st.session_state.ab_result
            trade_time_utc = res['trade_time_utc']
            row = res['row']
            
            st.markdown("#### 📊 상세 지표 비교")
            
            # 지표 추출용 헬퍼
            def get_val(res_dict, pattern):
                for k, v in res_dict.items():
                    if pattern in k: return v
                return 0

            comp_df = pd.DataFrame({
                "지표명": ["PASS1 Ratio", "WideTrend1", "WideTrend2", "TrendAvg", "CrossAvg", "FastRate", "PrevPriceRate(%)"],
                f"🅰️ {res['conf_a']}": [
                    get_val(res['res_a'], "PASS1"), get_val(res['res_a'], "wideTrendAvg (n"), get_val(res['res_a'], "wideTrendAvg2"),
                    get_val(res['res_a'], "trendAvg"), get_val(res['res_a'], "CrossAvg"), get_val(res['res_a'], "FastRate"),
                    get_val(res['res_a'], "PrevPriceRate")
                ],
                f"🅱️ {res['conf_b']}": [
                    get_val(res['res_b'], "PASS1"), get_val(res['res_b'], "wideTrendAvg (n"), get_val(res['res_b'], "wideTrendAvg2"),
                    get_val(res['res_b'], "trendAvg"), get_val(res['res_b'], "CrossAvg"), get_val(res['res_b'], "FastRate"),
                    get_val(res['res_b'], "PrevPriceRate")
                ]
            })
            st.table(comp_df)
            
            # --- 차트 함수 (UTC 기준 정렬 유지) ---
            def draw_chart(df, title, trade_time, row):
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
                
                # 중앙 정렬 (매수 전후 60분)
                view_before = 60
                view_after = 60
                start_v = trade_time - pd.Timedelta(minutes=view_before)
                end_v = trade_time + pd.Timedelta(minutes=view_after)
                
                df_v = df[(df['time'] >= start_v) & (df['time'] <= end_v)].copy()
                if df_v.empty: return go.Figure()

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3], subplot_titles=(title, ""))
                fig.add_trace(go.Candlestick(x=df_v['time'], open=df_v['open'], high=df_v['high'], low=df_v['low'], close=df_v['close'], name='Candle', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
                
                colors = ['#ef5350' if c >= o else '#26a69a' for c, o in zip(df_v['close'], df_v['open'])]
                fig.add_trace(go.Bar(x=df_v['time'], y=df_v['volume'], marker_color=colors, name='Volume'), row=2, col=1)
                
                buy_price = 0
                if 'bid_price_unit' in row and pd.notnull(row['bid_price_unit']) and row['bid_price_unit'] > 0:
                    buy_price = float(row['bid_price_unit'])
                else:
                    try:
                        closest_idx = (df_v['time'] - trade_time).abs().idxmin()
                        buy_price = df_v.loc[closest_idx]['close']
                    except: buy_price = 0

                if buy_price > 0:
                    fig.add_trace(go.Scatter(x=[trade_time], y=[buy_price], mode='markers', marker=dict(color='blue', size=15, symbol='triangle-up', line=dict(width=2, color='white')), name=f'Buy ({buy_price:,.0f})'), row=1, col=1)
                    fig.add_annotation(x=trade_time, y=buy_price, text="<b>BUY</b>", showarrow=True, arrowhead=2, ax=0, ay=30, bgcolor="white", bordercolor="blue", row=1, col=1)

                fig.add_vrect(x0=trade_time - pd.Timedelta(minutes=30), x1=trade_time, fillcolor="yellow", opacity=0.1, layer="below", line_width=0)
                fig.add_vline(x=trade_time, line_width=2, line_dash="dash", line_color="red")
                
                fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20), xaxis=dict(tickformat='%H:%M'))
                return fig

            st.plotly_chart(draw_chart(res['df_a'], f"🅰️ {res['conf_a']}", trade_time_utc, row), use_container_width=True)
            st.plotly_chart(draw_chart(res['df_b'], f"🅱️ {res['conf_b']}", trade_time_utc, row), use_container_width=True)

    # [Tab 6] AI 정밀 타점 분석기 (Cross-Timeframe Logic)
    with tab6:
        st.markdown("### 🧬 AI 정밀 타점 분석기 (1분봉 vs 기준분봉)")
        st.info("형님 전략의 핵심인 **'기준 분봉(3,5분)의 흐름 속에서 1분봉의 순간 파워'**를 계산합니다. 힘 없는 가짜 신호는 **Skip** 처리합니다.")
        
        ok_df = filtered_df[filtered_df['result'] == 'ok']
        fail_df = filtered_df[filtered_df['result'] == 'x']
        
        if len(ok_df) < 2 or len(fail_df) < 2:
            st.warning("⚠️ 분석을 위해 성공/실패 데이터가 각각 2건 이상 필요합니다.")
        else:
            with st.form("ai_cross_check_form"):
                st.markdown("#### 1️⃣ 기준 분봉 설정 (Base Timeframe)")
                target_intervals = st.multiselect("배경이 될 분봉", [3, 5, 10, 15, 30], default=[5, 10])
                
                st.markdown("#### 2️⃣ PASS 1 (눌림목/폭발) 정밀 설정")
                st.caption("👉 **공식:** (직전 1분봉 거래금) ÷ (기준 분봉 N개 평균 거래금)")
                
                c1, c2 = st.columns(2)
                with c1:
                    range_p1_n = st.slider("기준 분봉 N개 평균", 1, 20, (3, 10))
                with c2:
                    # PASS 1 비율 범위 (예: 0.5 = 1분봉이 평균의 50% 수준)
                    range_p1_ratio = st.slider("인정할 비율 범위 (Min~Max)", 0.0, 10.0, (0.1, 2.0), step=0.1)

                st.markdown("#### 3️⃣ 가짜 신호 Skip 조건 (체결강도 시뮬레이션)")
                st.caption("웹소켓을 대신하여, 1분봉의 상태를 보고 진입 여부를 결정합니다.")
                use_yangbong = st.checkbox("양봉일 때만 진입 (1분봉 Close > Open)", value=True)
                use_vol_up = st.checkbox("거래량 증가일 때만 진입 (현재 1분 > 직전 1분)", value=False)
                
                st.markdown("---")
                st.markdown("#### 4️⃣ 추세 지표 (Trend) 필터")
                range_w1 = st.slider("WideTrend1 (N값 탐색)", 5, 60, (10, 30), step=5)
                
                run_cross = st.form_submit_button("🚀 정밀 타점 시뮬레이션 시작")

            if run_cross:
                import itertools
                import time
                import numpy as np
                from src.fetcher import get_ohlcv
                from src.calculator import IndicatorCalculator # 기존 계산기도 쓰지만, PASS1은 여기서 직접 계산

                st.toast("1분봉과 기준 분봉을 교차 분석 중입니다...")
                
                # 데이터 캐싱 준비
                # 전수조사 대신 속도를 위해 30건씩 샘플링
                sample_ok = ok_df.head(30)
                sample_fail = fail_df.head(30)
                combined_samples = pd.concat([sample_ok, sample_fail])
                
                cached_data = {}
                progress_bar = st.progress(0)
                
                # 조합 생성: (분봉, N값_Pass1, N값_Wide1)
                list_p1 = list(range(range_p1_n[0], range_p1_n[1] + 1))
                list_w1 = list(range(range_w1[0], range_w1[1] + 1, 5))
                
                combinations = list(itertools.product(target_intervals, list_p1, list_w1))
                total_combs = len(combinations)
                
                results = []
                step = 0
                
                for combo in combinations:
                    interval, n_p1, n_w1 = combo
                    
                    # 카운터
                    cnt_ok_pass = 0    # 성공 케이스인데 조건 통과한 수 (Win)
                    cnt_fail_pass = 0  # 실패 케이스인데 조건 통과한 수 (Loss)
                    cnt_fail_skip = 0  # 실패 케이스인데 조건 안 맞아서 잘 거른 수 (Avoid)
                    cnt_ok_skip = 0    # 성공 케이스인데 조건 너무 빡빡해서 놓친 수 (Miss)
                    
                    for idx, row in combined_samples.iterrows():
                        market = row['market']
                        # UTC 시간 문제 해결
                        ts_str = str(row['timestamp'])
                        if '+' in ts_str: trade_time = pd.to_datetime(ts_str).tz_convert(None)
                        else: trade_time = pd.to_datetime(ts_str)
                        
                        log_24h = row.get('bid5_24h', 0)

                        # [1] 1분봉 데이터 가져오기 (디테일 확인용)
                        k_1m = (market, trade_time, 1)
                        if k_1m not in cached_data:
                            # 1분봉은 직전 상황 봐야 하므로 넉넉히
                            cached_data[k_1m] = get_ohlcv(market, trade_time, 1, 20)
                        df_1m = cached_data[k_1m]
                        
                        # [2] 기준 분봉 데이터 가져오기 (배경 확인용)
                        k_base = (market, trade_time, interval)
                        if k_base not in cached_data:
                            cached_data[k_base] = get_ohlcv(market, trade_time, interval, 100)
                        df_base = cached_data[k_base]
                        
                        if df_1m.empty or df_base.empty: continue
                        
                        # --- [형님의 PASS 1 로직 직접 구현] ---
                        # 1. 1분봉 파워 (직전 1분봉 거래대금) - 실제 체결된 봉 기준
                        # timestamp가 '진입 시점'이라면, 그 직전에 완성된 1분봉을 봐야 함 (iloc[-1] or -2 주의)
                        # 보통 백테스팅에선 iloc[-2]가 '직전 완성봉'
                        last_1m = df_1m.iloc[-2] 
                        vol_1m = last_1m['volume'] * last_1m['close'] # 거래대금 근사치
                        
                        # 2. 기준 분봉 배경 (N개 평균)
                        # df_base에서 N개 가져오기
                        if len(df_base) < n_p1 + 1: continue
                        base_subset = df_base.iloc[-(n_p1+1):-1] # 직전 완성봉들
                        avg_base_val = (base_subset['volume'] * base_subset['close']).mean()
                        
                        # 3. 비율 계산
                        if avg_base_val == 0: pass1_ratio = 0
                        else: pass1_ratio = vol_1m / avg_base_val
                        
                        # --- [필터링 1: 비율 조건] ---
                        if not (range_p1_ratio[0] <= pass1_ratio <= range_p1_ratio[1]):
                            # 범위 밖이면 진입 안함 (Skip)
                            if row['result'] == 'ok': cnt_ok_skip += 1
                            else: cnt_fail_skip += 1
                            continue

                        # --- [필터링 2: 체결강도 시뮬레이션 (Skip 조건)] ---
                        # 양봉 조건: 시가보다 종가가 높았나?
                        if use_yangbong and (last_1m['close'] <= last_1m['open']):
                            if row['result'] == 'ok': cnt_ok_skip += 1
                            else: cnt_fail_skip += 1
                            continue
                        
                        # 거래량 증가 조건
                        if use_vol_up:
                            prev_1m = df_1m.iloc[-3]
                            if last_1m['volume'] <= prev_1m['volume']:
                                if row['result'] == 'ok': cnt_ok_skip += 1
                                else: cnt_fail_skip += 1
                                continue
                                
                        # --- [필터링 3: 추세 지표 (WideTrend)] ---
                        # 이건 기존 계산기 활용
                        df_base.attrs['interval'] = interval
                        calc = IndicatorCalculator()
                        # WideTrend만 봅니다
                        p_sim = {'pass1_n': 3, 'wide_n': n_w1, 'wide2_n': 2, 'trend_n': 1, 'fast_n': 10}
                        res_ind = calc.calculate(df_base, df_1m, log_24h, p_sim)
                        if not res_ind: continue
                        
                        wd_val = res_ind.get(f"wideTrendAvg (n{n_w1})", 0)
                        
                        # WideTrend가 1.0 이상이어야 진입한다고 가정 (기본 필터)
                        if wd_val < 1.0:
                             if row['result'] == 'ok': cnt_ok_skip += 1
                             else: cnt_fail_skip += 1
                             continue

                        # --- [최종 진입] ---
                        # 여기까지 왔으면 매수 버튼 누른 것
                        if row['result'] == 'ok': cnt_ok_pass += 1
                        else: cnt_fail_pass += 1

                    # --- [점수 산정] ---
                    total_try = cnt_ok_pass + cnt_fail_pass
                    if total_try == 0: continue
                    
                    win_rate = cnt_ok_pass / total_try
                    # 실패 방어율: 원래 실패였던 애들 중 몇 개나 안 사고 넘겼나?
                    fail_total = len(sample_fail)
                    avoid_rate = cnt_fail_skip / fail_total if fail_total > 0 else 0
                    
                    score = (win_rate * 0.7) + (avoid_rate * 0.3)
                    
                    results.append({
                        "Score": score,
                        "설정": f"[{interval}분봉] vs 1분봉",
                        "PASS1_N": n_p1,
                        "Wide_N": n_w1,
                        "승률(Win Rate)": f"{win_rate*100:.1f}%",
                        "진입 횟수": total_try,
                        "실패 방어율": f"{avoid_rate*100:.1f}%",
                        "놓친 수익(Miss)": cnt_ok_skip
                    })
                    
                    step += 1
                    if step % 100 == 0:
                        progress_bar.progress(min(step / total_combs, 1.0))
                
                progress_bar.progress(1.0)
                
                if results:
                    df_res = pd.DataFrame(results).sort_values("Score", ascending=False)
                    best = df_res.iloc[0]
                    
                    st.success(f"🎉 찾았습니다! 1분봉의 '가짜 신호'를 가장 잘 걸러내는 설정입니다.")
                    
                    c_r1, c_r2, c_r3 = st.columns(3)
                    c_r1.metric("최적 기준 분봉", best['설정'])
                    c_r2.metric("PASS1 (평균 N개)", f"{best['PASS1_N']}개")
                    c_r3.metric("시뮬레이션 승률", best['승률(Win Rate)'])
                    
                    st.markdown("#### 🏆 정밀 타점 분석 결과 (Top 5)")
                    st.dataframe(df_res.head(5), width="stretch")
                    
                    st.info(f"""
                        💡 **형님, 이 결과가 의미하는 것:**
                        
                        **{best['설정']}** 배경에서 **이전 {best['PASS1_N']}개** 평균 대비 1분봉이 튀어오를 때,
                        양봉/거래량 조건을 걸고 들어가면 **실패 거래의 {best['실패 방어율']}**를 매수하지 않고 피할 수 있습니다.
                        
                        즉, **웹소켓으로 호가창을 보고 '힘 없다'고 판단해서 거르는 행위**를
                        이 설정(양봉 체크 + 비율 필터)으로 어느 정도 자동화할 수 있다는 뜻입니다.
                    """)
                else:
                    st.error("조건에 맞는 결과가 없습니다. 필터 범위를 조정해주세요.")


elif st.session_state.is_analyzed and st.session_state.df.empty:
    st.warning("⚠️ 데이터 매칭 실패")
