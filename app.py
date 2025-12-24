import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import glob
from src.parser import load_all_data

st.set_page_config(layout="wide", page_title="부자의 트레이딩 관제탑 (Real + Dist)")

st.title("🏯 부자의 트레이딩 관제탑 (종합 분석)")
st.markdown("---")

DATA_DIR = "data"
# 지표 분포용 색상 (수익=초록, 손실=빨강)
COLOR_MAP = {"Win": "#00CC96", "Loss": "#EF553B"}

# --- 사이드바 및 데이터 로드 ---
files = glob.glob(os.path.join(DATA_DIR, "acc_log.*.txt"))
available_dates = sorted([f.split("acc_log.")[1].replace(".txt", "") for f in files], reverse=True)

st.sidebar.header("📅 분석 기간 설정")

if not available_dates:
    st.sidebar.error("데이터 파일이 없습니다.")
else:
    mode = st.sidebar.radio("분석 모드", ["단일 날짜 (Daily)", "기간 종합 (History)"])
    selected_dates = [st.sidebar.selectbox("날짜 선택", available_dates)] if mode == "단일 날짜 (Daily)" else st.sidebar.multiselect("날짜 다중 선택", available_dates, default=available_dates)

    if st.sidebar.button("분석 시작 (Load Data)"):
        with st.spinner('실전 매매 기록을 분석 중입니다...'):
            df = load_all_data(DATA_DIR, selected_dates)
            
            if df.empty:
                st.warning("체결된 매매 기록을 찾을 수 없습니다.")
            else:
                # [전처리] 수익 여부에 따라 'Win/Loss' 라벨 생성 (지표 분포용)
                df['result_label'] = df['yield'].apply(lambda x: 'Win' if x > 0 else 'Loss')

                # --- 상단 요약 ---
                st.subheader(f"💰 자산 변동 리포트 ({len(selected_dates)}일간)")
                
                win_trades = len(df[df['yield'] > 0])
                total_trades = len(df)
                win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
                total_profit = df['profit_krw'].sum()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("총 매매", f"{total_trades}회")
                c2.metric("승률 (Win Rate)", f"{win_rate:.1f}%")
                c3.metric("누적 손익 (Net Profit)", f"{int(total_profit):,}원", delta_color="normal")
                c4.metric("평균 수익률", f"{df['yield'].mean():.2f}%", delta_color="normal")
                
                st.markdown("---")

                # --- 탭 구성 (분포 분석 부활!) ---
                tab1, tab2, tab3, tab4 = st.tabs(["📈 자산/수익 흐름", "📊 지표별 분포 (핵심)", "🎯 지표 vs 수익 (상세)", "📋 매매 일지"])

                # [Tab 1] 자산 곡선 & 수익률 히스토그램
                with tab1:
                    c_left, c_right = st.columns([2, 1])
                    with c_left:
                        df_sorted = df.sort_values('sell_time')
                        df_sorted['cumulative_profit'] = df_sorted['profit_krw'].cumsum()
                        fig_line = px.line(df_sorted, x='sell_time', y='cumulative_profit', 
                                           title="💸 내 계좌 우상향 그래프 (Cumulative)", markers=True)
                        fig_line.update_traces(line_color='#00CC96', line_width=3)
                        fig_line.add_hline(y=0, line_dash="dash", line_color="gray")
                        st.plotly_chart(fig_line, use_container_width=True)
                    
                    with c_right:
                        fig_hist = px.histogram(df, x="yield", nbins=30, title="수익률 분포 (Yield Hist)",
                                                color="yield", color_discrete_sequence=px.colors.diverging.RdYlGn)
                        st.plotly_chart(fig_hist, use_container_width=True)

                # [Tab 2] 지표별 분포 (형님이 원하시던 기능!)
                with tab2:
                    st.info("💡 **실제 수익(Win)과 손실(Loss)** 그룹 간의 지표 차이를 비교합니다.")
                    
                    numeric_cols = ['PASS1_Ratio', 'BID5_Ratio', 'trendAvg', 'wideTrendAvg', 'fastRate', 'upRate']
                    target_cols = [c for c in numeric_cols if c in df.columns]

                    # 반복문으로 모든 지표 렌더링
                    for col_name in target_cols:
                        st.markdown(f"### 📌 {col_name}")
                        c_h, c_b = st.columns([1, 1])
                        
                        # 히스토그램 (겹쳐보기)
                        with c_h:
                            fig_h = px.histogram(df, x=col_name, color="result_label", 
                                                 barmode="overlay", # 겹쳐서 비교
                                                 color_discrete_map=COLOR_MAP, 
                                                 opacity=0.6, nbins=30,
                                                 title=f"{col_name} 분포도 (Win vs Loss)")
                            st.plotly_chart(fig_h, use_container_width=True)
                        
                        # 박스플롯 (범위 비교)
                        with c_b:
                            fig_b = px.box(df, x="result_label", y=col_name, color="result_label",
                                           color_discrete_map=COLOR_MAP, points="all",
                                           title=f"{col_name} 통계 범위")
                            st.plotly_chart(fig_b, use_container_width=True)
                        st.markdown("---")

                # [Tab 3] 지표 vs 수익률 산점도 (Scatter)
                with tab3:
                    x_axis = st.selectbox("X축 지표 선택", target_cols)
                    fig_scat = px.scatter(df, x=x_axis, y="yield", 
                                          color="yield", color_continuous_scale="RdYlGn",
                                          size='buy_krw', 
                                          hover_data=['market', 'date', 'profit_krw'],
                                          title=f"{x_axis} 값이 높을수록 수익률도 높을까?")
                    fig_scat.add_hline(y=0, line_dash="dash", line_color="gray")
                    st.plotly_chart(fig_scat, use_container_width=True)

                # [Tab 4] 데이터 테이블
                with tab4:
                    disp_cols = ['date', 'market', 'result_label', 'yield', 'profit_krw', 'buy_krw', 'sell_time'] + target_cols
                    
                    def highlight_yield(val):
                        color = 'red' if val < 0 else 'green'
                        return f'color: {color}'

                    st.dataframe(
                        df[disp_cols].sort_values('sell_time', ascending=False).style.applymap(highlight_yield, subset=['yield', 'profit_krw']),
                        use_container_width=True
                    )