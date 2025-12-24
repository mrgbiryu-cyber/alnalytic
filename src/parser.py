import re
import pandas as pd
from datetime import datetime
import os

def parse_single_day(acc_path, date_str):
    """
    acc_log에서 매수(Bid)와 매도(Ask) 쌍을 찾아 수익률을 계산하고,
    진입 시점의 지표(PASS1, Trend 등)를 매칭합니다.
    """
    if not os.path.exists(acc_path):
        return pd.DataFrame()

    # 1. 임시 저장소
    market_state = {}     # 각 코인의 실시간 지표 상태 저장 (CCTV)
    open_positions = {}   # 매수 후 매도 대기 중인 상태 { 'KRW-BTC': { 'buy_price': 10000, 'buy_time': ... } }
    completed_trades = [] # 매도까지 완료된 거래 기록

    # 2. 로그 읽기
    with open(acc_path, 'r', encoding='utf-8') as f:
        for line in f:
            # 시간 파싱
            time_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
            if not time_match: continue
            
            current_time_str = f"{date_str} {time_match.group(1)}"
            try:
                current_dt = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M:%S.%f")
            except:
                continue # 날짜 파싱 에러 시 스킵

            # 마켓 추출
            market_match = re.search(r'(KRW-[A-Z0-9]+)', line)
            market = market_match.group(1) if market_match else None

            # -----------------------------------------------------------
            # [A] 지표 파싱 (매수 전 상태를 알기 위해 계속 업데이트)
            # -----------------------------------------------------------
            if market:
                if market not in market_state: market_state[market] = {}
                
                # 정규식 패턴 모음
                patterns = {
                    'pass1_avg': r'prevAccTradePrice12Avg.*?/\s*([\d\.E]+)',
                    'pass1_1min': r'getAccTradePrice1min\(\).*?/\s*([\d\.E]+)',
                    'bid5_24h': r'getAccTradePrice24h\(\).*?/\s*([\d\.E]+)',
                    'bid5_total': r'total candles acc trade price.*?/\s*([\d\.E]+)',
                    'wideTrendAvg': r'wideTrendAvg\s*:\s*([\d\.]+)',
                    'trendAvg': r'trendAvg\s*:\s*([\d\.]+)',
                    'fastRate': r'fastRate\s*:\s*([\d\.\-]+)',
                    'upRate': r'upRate\s*:\s*([\d\.\-]+)'
                }
                
                for key, pat in patterns.items():
                    if key in line or (key == 'pass1_avg' and 'prevAccTradePrice12Avg' in line):
                        val = re.search(pat, line)
                        if val: market_state[market][key] = float(val.group(1))

            # -----------------------------------------------------------
            # [B] 매수(BUY) 감지 - JSON 로그
            # -----------------------------------------------------------
            # {"uuid":..., "side":"bid", "ord_type":"price", "price":"10183", ... "market":"KRW-KAVA"}
            if 'OrdersServiceImpl.bidOrder' in line and '"side":"bid"' in line:
                try:
                    # JSON 파싱 대신 정규식으로 안전하게 추출
                    price_match = re.search(r'"price":"([\d\.]+)"', line)
                    market_json_match = re.search(r'"market":"(KRW-[A-Z0-9]+)"', line)
                    
                    if price_match and market_json_match:
                        buy_market = market_json_match.group(1)
                        total_buy_krw = float(price_match.group(1)) # 매수 투입 금액 (예: 10183원)
                        
                        # 현재 지표 상태 스냅샷 뜨기
                        state = market_state.get(buy_market, {}).copy()
                        
                        # 지표 계산 (Ratio 등)
                        p1_1min = state.get('pass1_1min', 0)
                        p1_avg = state.get('pass1_avg', 0)
                        state['PASS1_Ratio'] = p1_1min / p1_avg if p1_avg > 0 else 0
                        
                        b5_total = state.get('bid5_total', 0)
                        b5_24h = state.get('bid5_24h', 0)
                        state['BID5_Ratio'] = b5_total / b5_24h if b5_24h > 0 else 0

                        # 매수 포지션 등록
                        open_positions[buy_market] = {
                            'buy_time': current_dt,
                            'buy_krw': total_buy_krw,
                            'indicators': state
                        }
                except Exception as e:
                    print(f"Buy Parse Error: {e}")

            # -----------------------------------------------------------
            # [C] 매도(SELL) 주문 감지 - JSON 로그
            # -----------------------------------------------------------
            # {"uuid":..., "side":"ask", ... "market":"KRW-0G", ... "volume":"4.07272012"}
            if 'OrdersServiceImpl.askOrder' in line and '"side":"ask"' in line:
                try:
                    vol_match = re.search(r'"volume":"([\d\.]+)"', line)
                    market_json_match = re.search(r'"market":"(KRW-[A-Z0-9]+)"', line)
                    
                    if vol_match and market_json_match:
                        sell_market = market_json_match.group(1)
                        sell_volume = float(vol_match.group(1)) # 매도한 코인 개수
                        
                        # 매수 포지션이 있는지 확인 (짝 맞추기)
                        if sell_market in open_positions:
                            open_positions[sell_market]['pending_sell_volume'] = sell_volume
                            open_positions[sell_market]['sell_start_time'] = current_dt
                except:
                    pass

            # -----------------------------------------------------------
            # [D] 매도(SELL) 체결가 확정 - 텍스트 로그
            # -----------------------------------------------------------
            # down ask KRW-0G / 2472.768
            # highest ask KRW-0G / 2413.0 / ...
            if 'AskMonitoringServiceImpl' in line and (' ask ' in line):
                # 패턴: (down ask|up ask|highest ask) (KRW-XXX) / (PRICE)
                match = re.search(r'(down ask|up ask|highest ask)\s+(KRW-[A-Z0-9]+)\s*/\s*([\d\.]+)', line)
                if match:
                    sell_type = match.group(1)
                    market = match.group(2)
                    sell_price_per_coin = float(match.group(3)) # 매도 단가
                    
                    # 매도 대기 중인 포지션이 있으면 정산
                    if market in open_positions and 'pending_sell_volume' in open_positions[market]:
                        pos = open_positions.pop(market) # 포지션 꺼내기 (완료 처리)
                        
                        buy_krw = pos['buy_krw']
                        sell_vol = pos['pending_sell_volume']
                        
                        # 수익금 계산: (매도단가 * 개수) - 매수총액
                        sell_total_krw = sell_price_per_coin * sell_vol
                        profit_krw = sell_total_krw - buy_krw
                        yield_pct = (profit_krw / buy_krw) * 100 if buy_krw > 0 else 0
                        
                        # 결과 저장
                        trade_data = {
                            'date': date_str,
                            'market': market,
                            'buy_time': pos['buy_time'],
                            'sell_time': current_dt,
                            'buy_krw': buy_krw,
                            'sell_krw': sell_total_krw,
                            'profit_krw': profit_krw,
                            'yield': yield_pct,
                            'result': 'ok' if profit_krw > 0 else 'x', # 수익이면 ok, 손실이면 x
                            'sell_type': sell_type
                        }
                        # 지표 병합
                        trade_data.update(pos['indicators'])
                        completed_trades.append(trade_data)

    return pd.DataFrame(completed_trades)

def load_all_data(data_dir, date_list):
    """여러 날짜의 데이터를 통합 로드"""
    all_dfs = []
    for date_str in date_list:
        acc_file = os.path.join(data_dir, f"acc_log.{date_str}.txt")
        if os.path.exists(acc_file):
            df = parse_single_day(acc_file, date_str)
            if not df.empty:
                all_dfs.append(df)
    
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    else:
        return pd.DataFrame()