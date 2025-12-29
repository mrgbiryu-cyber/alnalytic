import re
import pandas as pd
from datetime import datetime
import os
import json

def parse_single_day_expi(acc_path, date_str):
    clean_date_str = date_str[:10]

    patterns = {
        'pass1_avg': re.compile(r'PASS 1 prevAccTradePrice12Avg\s+KRW.*\/ ([\d\.E\+\-]+)'),
        'pass1_cur': re.compile(r'PASS 1 targetVo\.getAccTradePrice1min\(\).*\/ ([\d\.E\+\-]+)'),
        'wideTrendAvg': re.compile(r'wideTrendAvg\s*:\s*([\d\.E\+\-]+)'),
        'wideTrendAvg2': re.compile(r'wideTrendAvg2\s*:\s*([\d\.E\+\-]+)'),
        'crossAvg': re.compile(r'BID crossAvg\s*:\s*([\d\.E\+\-]+)'),
        'trendAvg': re.compile(r'trendAvg\s*:\s*([\d\.E\+\-]+)'),
        'upRate': re.compile(r'BID upRate\s*:\s*([\d\.E\+\-]+)'),
        'fastRate': re.compile(r'fastRate\s*:\s*([\d\.E\+\-]+)'),
        'bid5_24h': re.compile(r'BID 5 targetVo\.getAccTradePrice24h\(\).*\/ ([\d\.E\+\-]+)'),
        'bid5_prev': re.compile(r'BID 5 prevAccTradePrice.*\/ ([\d\.E\+\-]+)'),
    }

    # price 2 패턴 (공백 및 형식에 유연하게 대응)
    price2_pattern = re.compile(r'price 2\s*:\s*[A-Z0-9-]+\s*/\s*([\d\.E\+\-]+)\s*/\s*([\d\.E\+\-]+)')

    live_state = {}
    last_pass = {}
    pending_trades = {}
    final_data = []

    if not os.path.exists(acc_path): 
        return pd.DataFrame()

    with open(acc_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue

            time_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
            if not time_match: continue
            current_dt = datetime.strptime(f"{clean_date_str} {time_match.group(1)}", "%Y-%m-%d %H:%M:%S.%f")

            market_match = re.search(r'(KRW-[A-Z0-9]+)', line)
            market = market_match.group(1) if market_match else None

            if market:
                if market not in live_state: live_state[market] = {}
                for key, pattern in patterns.items():
                    m = pattern.search(line)
                    if m:
                        try: live_state[market][key] = float(m.group(1))
                        except: pass
                
                # price 2 매칭 및 계산 (금액 1 / (금액 2 * 2))
                m_p2 = price2_pattern.search(line)
                if m_p2:
                    try:
                        val1 = float(m_p2.group(1))
                        val2 = float(m_p2.group(2))
                        live_state[market]['price'] = val1 / (val2 * 2) if val2 != 0 else 0
                    except: pass

            if 'BID PASS 7 minus 2 candles' in line and market:
                snapshot = live_state.get(market, {}).copy()
                snapshot['market'] = market
                snapshot['pass_time'] = current_dt
                p1_c = snapshot.get('pass1_cur', 0); p1_a = snapshot.get('pass1_avg', 0)
                snapshot['PASS1_Ratio'] = p1_c / p1_a if p1_a != 0 else 0
                b5_p = snapshot.get('bid5_prev', 0); b5_24 = snapshot.get('bid5_24h', 0)
                snapshot['BID5_Ratio'] = b5_p / b5_24 if b5_24 != 0 else 0
                last_pass[market] = snapshot

            # 매수 주문 시 투자 금액(KRW) 추출
            if '"side":"bid"' in line:
                try:
                    json_str = line.split(' - ')[-1]
                    order_data = json.loads(json_str)
                    mkt = order_data.get('market')
                    if mkt and mkt in last_pass:
                        trade_info = last_pass[mkt].copy()
                        trade_info['bid_time'] = current_dt
                        trade_info['invested_krw'] = float(order_data.get('price', 0))
                        
                        # 매수 시점의 가장 최신 price 정보 반영
                        if mkt in live_state and 'price' in live_state[mkt]:
                            trade_info['price'] = live_state[mkt]['price']
                            
                        pending_trades[mkt] = trade_info
                except: pass

            # 실제 매수 단가 추출
            if 'bid trade price' in line and market:
                price_match = re.search(r'/\s*([\d\.]+)', line)
                if price_match and market in pending_trades:
                    pending_trades[market]['bid_price_unit'] = float(price_match.group(1))

            # 매도 시작 신호 포착
            if 'ASK start' in line and market:
                if market in pending_trades:
                    pending_trades[market]['is_asking'] = True

            # 실제 매도 단가 추출 (ASK start 이후의 trade price를 임시 저장)
            if 'trade price' in line and market and 'bid' not in line:
                if market in pending_trades and pending_trades[market].get('is_asking'):
                    price_match = re.search(r'/\s*([\d\.]+)', line)
                    if not price_match:
                        price_match = re.search(r'price\s+([\d\.]+)\s+/', line)
                    
                    if price_match:
                        pending_trades[market]['temp_ask_price'] = float(price_match.group(1))

            # 매도 주문 JSON 로그가 찍힐 때 최종 확정
            if '"side":"ask"' in line:
                try:
                    json_str = line.split(' - ')[-1]
                    order_data = json.loads(json_str)
                    mkt = order_data.get('market')
                    if mkt and mkt in pending_trades:
                        trade = pending_trades.pop(mkt)
                        volume = float(order_data.get('volume', 0))
                        ask_price_unit = trade.get('temp_ask_price', 0)
                        bid_unit = trade.get('bid_price_unit', 0)
                        
                        if bid_unit > 0 and ask_price_unit > 0:
                            trade['profit_rate'] = (ask_price_unit - bid_unit) / bid_unit * 100
                            trade['profit_krw'] = (ask_price_unit - bid_unit) * volume - (trade.get('invested_krw', 0) * 0.001)
                            trade['result'] = 'ok' if ask_price_unit > bid_unit else 'x' if ask_price_unit < bid_unit else 'NB'
                        else:
                            trade['profit_rate'] = 0; trade['profit_krw'] = 0; trade['result'] = 'NB'
                        
                        trade['ask_price'] = ask_price_unit
                        trade['volume'] = volume
                        trade['timestamp'] = current_dt
                        trade['date'] = clean_date_str
                        final_data.append(trade)
                        continue
                except: pass

            # 기존 매도 결과 처리 로직 (백업용)
            ask_match = re.search(r'(up ask|down ask|highest ask)\s+(KRW-[A-Z0-9]+)', line)
            if ask_match:
                mkt = ask_match.group(2)
                if mkt in pending_trades:
                    trade = pending_trades.pop(mkt)
                    prices = re.findall(r'/\s*([\d\.]+)', line)
                    ask_price_unit = float(prices[-1]) if prices else trade.get('temp_ask_price', 0)
                    
                    bid_unit = trade.get('bid_price_unit', 0)
                    volume = trade.get('volume', 0)
                    
                    if bid_unit > 0 and ask_price_unit > 0:
                        trade['profit_rate'] = (ask_price_unit - bid_unit) / bid_unit * 100
                        trade['profit_krw'] = (ask_price_unit - bid_unit) * volume - (trade.get('invested_krw', 0) * 0.001)
                        trade['result'] = 'ok' if ask_price_unit > bid_unit else 'x' if ask_price_unit < bid_unit else 'NB'
                    else:
                        trade['profit_rate'] = 0; trade['profit_krw'] = 0; trade['result'] = 'NB'
                    
                    trade['ask_price'] = ask_price_unit
                    trade['timestamp'] = current_dt
                    trade['date'] = clean_date_str
                    final_data.append(trade)

    if not final_data: return pd.DataFrame()
    result_df = pd.DataFrame(final_data)
    cols = ['date', 'timestamp', 'market', 'result', 'profit_rate', 'profit_krw', 'invested_krw', 'price', 'PASS1_Ratio', 'BID5_Ratio', 
            'wideTrendAvg', 'wideTrendAvg2', 'crossAvg', 'trendAvg', 'upRate', 'fastRate', 'bid_price_unit', 'ask_price', 'volume']
    
    # 필수 컬럼 보장
    for c in cols:
        if c not in result_df.columns:
            result_df[c] = None
            
    return result_df[cols]

def load_all_data(data_dir, date_list):
    all_dfs = []
    for date_str in date_list:
        patterns = [f"acc_log.{date_str}.txt", f"acc_log.{date_str}.txt.log", f"acc_log.{date_str}.log"]
        for p in patterns:
            acc_path = os.path.join(data_dir, p)
            if os.path.exists(acc_path):
                df = parse_single_day_expi(acc_path, date_str)
                if not df.empty: all_dfs.append(df)
                break
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
