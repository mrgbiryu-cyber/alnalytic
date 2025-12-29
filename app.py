import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import io  # 엑셀 변환을 위한 모듈
from datetime import datetime
from src.parser import load_all_data

st.set_page_config(layout="wide", page_title="부자의 트레이딩 분석기 (Expi)")

st.title("🧪 전략 시뮬레이션 분석기 (Expi Mode)")
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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 지표 분포", "🕸️ 패턴 찾기 (Parallel)", "🔍 상관관계", "📋 원본 데이터"])

    numeric_cols = [
        'profit_rate', 'PASS1_Ratio', 'BID5_Ratio', 
        'wideTrendAvg', 'wideTrendAvg2', 'crossAvg', 
        'trendAvg', 'upRate', 'fastRate'
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
        st.dataframe(filtered_df.sort_values(['date', 'timestamp'], ascending=False), use_container_width=True)

elif st.session_state.is_analyzed and st.session_state.df.empty:
    st.warning("⚠️ 데이터 매칭 실패")