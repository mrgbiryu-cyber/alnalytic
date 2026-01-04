import pandas as pd
from src.fetcher import get_ohlcv
from datetime import datetime, timedelta

# ==========================================
# [설정] 여기에 분석하고 싶은 로그 내용을 적어주세요
# ==========================================
MARKET = "KRW-OPEN"            # 예: 로그에 찍힌 코인명
TARGET_TIME = "2025-12-30 00:08:47" # 예: 로그에 찍힌 매수 시간 (bid_time)
LOG_PASS1_VALUE = 0.086      # 예: 로그에 찍힌 PASS1_Ratio 값 (비교용)
BASE_MIN = 5                  # 예: 3분봉 기준
PASS1_N = 1                   # 예: 3분봉 2개 평균 (12분, 9분)
# ==========================================

print(f"\n🕵️‍♂️ [정밀 진단 시작] {MARKET} / {TARGET_TIME}")
trade_time = pd.to_datetime(TARGET_TIME)

# 1. API 데이터 호출 (넉넉하게 가져옴)
print("\n1. 업비트 API 데이터 호출 중...")
df_base = get_ohlcv(MARKET, trade_time, interval_min=BASE_MIN, count=10)
df_1m = get_ohlcv(MARKET, trade_time, interval_min=1, count=10)

# 2. 데이터 확인 (눈으로 확인해야 함)
print(f"\nCreating Trace for {BASE_MIN}-min Candles (df_base):")
# 시간, 거래량만 깔끔하게 출력
print(df_base[['time', 'volume']].tail(5).to_string())

print(f"\nCreating Trace for 1-min Candles (df_1m):")
print(df_1m[['time', 'volume']].tail(5).to_string())

# 3. 계산 로직 검증 (PASS1)
print("\n2. PASS1 계산 추적")

# (1) 분자: 1분봉 거래대금
# API가 가져온 마지막 1분봉이 '매수 시간'과 일치하는지, 아니면 그 전인지 확인
cur_1m = df_1m.iloc[-1]
print(f"👉 사용된 1분봉(분자): {cur_1m['time']} | 거래량: {cur_1m['volume']:.2f}")

# (2) 분모: 기준 분봉 평균 (형님 말씀: 3분봉 2개 -> 12분, 9분)
# 현재 로직대로 뒤에서 N개 가져오기
print(f"\n👉 [검증 A] 현재 로직 (iloc[-{PASS1_N}:]) 으로 가져온 캔들:")
candles_A = df_base.iloc[-PASS1_N:]
print(candles_A[['time', 'volume']].to_string())
avg_A = candles_A['volume'].mean()
ratio_A = cur_1m['volume'] / avg_A
print(f"   => 결과 A: {ratio_A:.4f} (로그값 {LOG_PASS1_VALUE} 와 비교)")

# (3) 시프트 검증 (혹시 현재 진행중인 봉을 가져왔나?)
print(f"\n👉 [검증 B] 한 칸 전으로 밀어서 가져온 캔들 (iloc[-{PASS1_N+1}:-1]):")
candles_B = df_base.iloc[-(PASS1_N+1):-1]
print(candles_B[['time', 'volume']].to_string())
avg_B = candles_B['volume'].mean()
ratio_B = cur_1m['volume'] / avg_B
print(f"   => 결과 B: {ratio_B:.4f} (로그값 {LOG_PASS1_VALUE} 와 비교)")

print("\n------------------------------------------------")
if abs(ratio_A - LOG_PASS1_VALUE) < abs(ratio_B - LOG_PASS1_VALUE):
    print("결론: [검증 A]가 더 가깝습니다. (현재 로직이 맞거나, 로그도 최신봉을 포함함)")
else:
    print("결론: [검증 B]가 더 가깝습니다. (현재 로직이 '진행 중인 봉'을 포함해서 오차 발생)")
    print("      -> 해결책: Calculator에서 슬라이싱을 한 칸 뒤로 미뤄야 합니다.")
print("------------------------------------------------")