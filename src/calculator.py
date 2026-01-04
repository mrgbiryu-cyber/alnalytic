import pandas as pd
import numpy as np

class IndicatorCalculator:
    def __init__(self):
        pass

    def calculate(self, df_base, df_1m, log_24h_vol=0, params=None):
        if params is None:
            params = {}
        
        # 파라미터 가져오기 (기본값 설정)
        pass1_n = params.get('pass1_n', 3)
        wide_n = params.get('wide_n', 17)  # Wide1 기본값
        wide2_n = params.get('wide2_n', 3) # Wide2 기본값
        trend_n = params.get('trend_n', 2)
        fast_n = params.get('fast_n', 24)

        # 데이터 유효성 검사
        if df_base is None or df_base.empty or len(df_base) < (wide_n * 2 + 5):
            return {}

        # 1. PASS1_Ratio (거래량 비율)
        # df_1m이 비어있으면 0 처리
        if df_1m is not None and len(df_1m) >= 2:
            # [수정] 현재 진행중인 1분봉(-1)이 아니라, '직전 완성된 1분봉(-2)'의 거래대금을 사용
            cur_1m_vol = df_1m.iloc[-2]['volume'] 
        elif df_1m is not None and not df_1m.empty:
            cur_1m_vol = df_1m.iloc[-1]['volume']
        else:
            cur_1m_vol = 0
            
        # 기준 분봉(df_base)의 직전 N개 평균 거래량 (거래대금)
        # 수정: 인덱싱 범위를 [-(n+1) : -1]로 하여 '진행중인 봉' 제외하고 '직전 완성봉'부터 N개를 가져옴
        base_vol_avg_N = df_base['volume'].iloc[-(pass1_n + 1):-1].mean()
        
        # 분모가 0이거나 데이터가 없으면 방어 처리
        if base_vol_avg_N > 0:
            pass1_ratio = cur_1m_vol / base_vol_avg_N
        else:
            pass1_ratio = 0

        # 2. BID5_Ratio (직전 2개 캔들 거래량 합 / 24시간 거래량)
        bid_sum_2 = df_base['volume'].iloc[-3:-1].sum()
        final_24h_vol = log_24h_vol if log_24h_vol > 0 else df_base['volume'].sum()
        bid5_ratio = bid_sum_2 / final_24h_vol if final_24h_vol > 0 else 0

        # 3. wideTrendAvg (Wide1 - 장기)
        ma_curr = df_base['close'].iloc[-(wide_n+1):-1].mean()
        ma_prev = df_base['close'].iloc[-(2*wide_n+1):-(wide_n+1)].mean()
        wide_trend = ma_curr / ma_prev if ma_prev > 0 else 1.0

        # 4. wideTrendAvg2 (Wide2 - 중기)
        ma2_curr = df_base['close'].iloc[-(wide2_n+1):-1].mean()
        ma2_prev = df_base['close'].iloc[-(2*wide2_n+1):-(wide2_n+1)].mean()
        wide_trend2 = ma2_curr / ma2_prev if ma2_prev > 0 else 1.0

        # 5. trendAvg (Trend - 단기)
        trend_curr = df_base['close'].iloc[-(trend_n+1):-1].mean()
        trend_prev = df_base['close'].iloc[-(2*trend_n+1):-(trend_n+1)].mean()
        trend_avg_val = trend_curr / trend_prev if trend_prev > 0 else 1.0

        # 6. CrossAvg (이격도: Trend / Wide1)
        # Trend(단기) / Wide1(장기) -> 값이 1보다 크면 단기가 장기보다 높음(골든크로스 방향)
        cross_avg = trend_curr / ma_curr if ma_curr > 0 else 1.0

        # 7. FastRate (고점 대비 하락률)
        window_fast = df_base.iloc[-(fast_n + 1):-1]
        if not window_fast.empty:
            max_vol_idx_rel = window_fast['volume'].argmax()
            max_vol_idx_abs = window_fast.index[max_vol_idx_rel]
            target_idx = max_vol_idx_abs - 2 # 고점 2칸 전
            
            if target_idx in df_base.index:
                max_vol = df_base.loc[max_vol_idx_abs]['volume']
                target_vol = df_base.loc[target_idx]['volume']
                fast_rate = (target_vol - max_vol) / max_vol if max_vol > 0 else 0
            else:
                fast_rate = 0
        else:
            fast_rate = 0

        # 8. upRate (Volume 변동률)
        vol_prev = df_base.iloc[-2]['volume']
        vol_prev_2 = df_base.iloc[-3]['volume']
        up_rate = (vol_prev - vol_prev_2) / vol_prev_2 if vol_prev_2 > 0 else 0

        # 9. PrevPriceRate (직전 캔들 가격 등락률 %)
        close_prev = df_base.iloc[-2]['close']   # 직전 봉 종가
        close_prev_2 = df_base.iloc[-3]['close'] # 전전 봉 종가
        price_rate = ((close_prev - close_prev_2) / close_prev_2) * 100 if close_prev_2 > 0 else 0

        return {
            f"PASS1_Ratio (avg{pass1_n})": pass1_ratio, # 0
            "BID5_Ratio": bid5_ratio,                   # 1
            f"wideTrendAvg (n{wide_n})": wide_trend,    # 2
            f"wideTrendAvg2 (n{wide2_n})": wide_trend2, # 3
            f"trendAvg (n{trend_n})": trend_avg_val,    # 4
            "CrossAvg": cross_avg,                      # 5
            f"FastRate (range{fast_n})": fast_rate,     # 6
            "upRate(Vol)": up_rate,                     # 7
            "PrevPriceRate(%)": price_rate,             # 8
            "settings": f"{df_base.attrs.get('interval')}분" # 9
        }
