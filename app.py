import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
from src.parser import load_all_data

st.set_page_config(layout="wide", page_title="부자의 트레이딩 분석기 (Expi)")

st.title("🧪 전략 시뮬레이션 분석기 (Expi Mode)")
st.markdown("---")

DATA_DIR = "data"
# 결과 색상 매핑 (ok:초록, x:빨강, NB:파랑, unknown:회색)
COLOR_MAP = {"ok": "#00CC96", "x": "#EF553B", "NB": "#636EFA", "unknown": "gray"}

# --- [핵심] 세션 상태 초기화 (데이터 기억 장치) ---
# 이 부분이 없으면 버튼 누를 때마다 데이터가 날아갑니다.
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'is_analyzed' not in st.session_state:
    st.session_state.is_analyzed = False

# 파일 자동 스캔
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

files = glob.glob(os.path.join(DATA_DIR, "acc_log.*.txt"))
available_dates = sorted([f.split("acc_log.")[1].replace(".txt", "") for f in files], reverse=True)

st.sidebar.header("📅 데이터 로드")
if not available_dates:
    st.sidebar.error(f"'{DATA_DIR}' 폴더에 로그 파일이 없습니다.")
else:
    mode = st.sidebar.radio("분석 모드", ["단일 날짜", "기간 종합"])
    
    # 날짜 선택
    if mode == "단일 날짜":
        s_date = st.sidebar.selectbox("날짜", available_dates)
        selected_dates = [s_date]
    else:
        selected_dates = st.sidebar.multiselect("날짜", available_dates, default=available_dates) # 기본값 전체 선택

    # 분석 버튼 클릭 시
    if st.sidebar.button("🚀 분석 시작"):
        with st.spinner('로그 분석 중...'):
            # 데이터 로드 후 세션에 저장 (새로고침 방지)
            raw_df = load_all_data(DATA_DIR, selected_dates)
            st.session_state.df = raw_df
            st.session_state.is_analyzed = True # "분석 했음" 상태값 설정

# --- 메인 화면 렌더링 (세션에 데이터가 있을 때만 실행) ---
if st.session_state.is_analyzed and not st.session_state.df.empty:
    df = st.session_state.df # 세션에서 데이터 꺼내오기

    # 필터링 (사이드바 동작 시에도 데이터 유지됨)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔎 결과 필터")
    
    # 결과 필터 (ok, x, NB 등)
    all_results = sorted(df['result'].unique())
    res_filter = st.sidebar.multiselect("결과 포함", all_results, default=all_results)
    
    # 데이터 필터 적용
    filtered_df = df[df['result'].isin(res_filter)]

    # 상단 요약 정보
    c1, c2, c3, c4 = st.columns(4)
    ok_cnt = len(filtered_df[filtered_df['result']=='ok'])
    x_cnt = len(filtered_df[filtered_df['result']=='x'])
    total_cnt = len(filtered_df)
    win_rate = (ok_cnt / (ok_cnt + x_cnt) * 100) if (ok_cnt + x_cnt) > 0 else 0
    
    c1.metric("Total Count", total_cnt)
    c2.metric("OK (성공)", ok_cnt)
    c3.metric("X (실패)", x_cnt)
    c4.metric("Win Rate", f"{win_rate:.1f}%")
    st.markdown("---")

    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 지표 분포", "🌐 종합 흐름", "🔍 상관관계 (Scatter)", "📋 원본 데이터"])

    # 분석 대상 지표 목록
    numeric_cols = ['PASS1_Ratio', 'BID5_Ratio', 'trendAvg', 'wideTrendAvg', 'wideTrendAvg2', 'fastRate', 'upRate', 'crossAvg']
    target_cols = [c for c in numeric_cols if c in filtered_df.columns]

    # [Tab 1] 지표 분포 (Histogram & Box Plot)
    with tab1:
        st.info("각 지표별로 성공(ok)과 실패(x)가 어떤 분포를 보이는지 확인하세요.")
        for col in target_cols:
            st.markdown(f"#### {col}")
            c_h, c_b = st.columns(2)
            with c_h:
                fig_h = px.histogram(filtered_df, x=col, color="result", 
                                     barmode="overlay", color_discrete_map=COLOR_MAP, 
                                     opacity=0.6, title=f"{col} 분포도")
                st.plotly_chart(fig_h, use_container_width=True)
            with c_b:
                fig_b = px.box(filtered_df, x="result", y=col, color="result", 
                               color_discrete_map=COLOR_MAP, title=f"{col} 범위 비교")
                st.plotly_chart(fig_b, use_container_width=True)
            st.markdown("---")

    # [Tab 2] Parallel Coordinates (다차원 분석)
    with tab2:
        st.markdown("##### 🕸️ 여러 지표를 한눈에 (Parallel Coordinates)")
        if len(filtered_df) > 0:
            p_df = filtered_df.copy()
            # 색상 매핑을 위해 숫자 변환 (ok=1, x=0, 그외=0.5)
            p_df['color_val'] = p_df['result'].map({'ok':1, 'x':0}).fillna(0.5)
            
            fig_p = px.parallel_coordinates(
                p_df, 
                dimensions=target_cols[:6], # 너무 많으면 복잡하므로 6개만
                color="color_val", 
                range_color=[0,1], 
                color_continuous_scale=[(0,"#EF553B"), (0.5,"gray"), (1,"#00CC96")]
            )
            st.plotly_chart(fig_p, use_container_width=True)

    # [Tab 3] Scatter Plot (상관관계 분석) - 여기가 핵심!
    with tab3:
        st.markdown("##### 🔍 지표 간 상관관계 분석")
        st.info("💡 **X축과 Y축을 변경해도 데이터가 초기화되지 않습니다.**")
        
        c_x, c_y = st.columns(2)
        with c_x:
            # 기본값 설정
            default_x = target_cols.index('wideTrendAvg') if 'wideTrendAvg' in target_cols else 0
            x_axis = st.selectbox("X축 지표", target_cols, index=default_x, key="scatter_x") 
        with c_y:
            default_y = target_cols.index('trendAvg') if 'trendAvg' in target_cols else 0
            y_axis = st.selectbox("Y축 지표", target_cols, index=default_y, key="scatter_y")
        
        if x_axis and y_axis:
            fig_s = px.scatter(
                filtered_df, 
                x=x_axis, y=y_axis, 
                color="result",
                color_discrete_map=COLOR_MAP,
                hover_data=['market', 'timestamp', 'PASS1_Ratio', 'BID5_Ratio'],
                title=f"{x_axis} vs {y_axis} 상관관계"
            )
            st.plotly_chart(fig_s, use_container_width=True)

    # [Tab 4] 원본 데이터 (Grid)
    with tab4:
        st.markdown("##### 📋 분석된 데이터 목록")
        st.dataframe(
            filtered_df.sort_values(['date', 'timestamp'], ascending=False), 
            use_container_width=True
        )

# 분석된 데이터가 없을 때 메시지
elif st.session_state.is_analyzed and st.session_state.df.empty:
    st.warning("⚠️ 분석 가능한 데이터가 없습니다. (Acc로그와 Expi로그 매칭 실패)")