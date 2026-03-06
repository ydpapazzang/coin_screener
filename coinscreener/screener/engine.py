import pyupbit
import pandas as pd
import time

def get_ohlcv_with_retry(ticker, interval, count=200, retries=3, delay=0.3):
    """API 호출 제한을 고려하여 재시도 로직이 포함된 OHLCV 조회"""
    for i in range(retries):
        # 업비트 초당 호출 제한을 피하기 위한 최소한의 지연
        time.sleep(0.1) 
        df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
        if df is not None:
            return df
        time.sleep(delay * (i + 1))
    return None

def calculate_rsi(ohlc: pd.DataFrame, period: int = 14):
    delta = ohlc["close"].diff()
    ups, downs = delta.copy(), delta.copy()
    ups[ups < 0] = 0
    downs[downs > 0] = 0

    au = ups.ewm(com=period - 1, min_periods=period).mean()
    ad = downs.abs().ewm(com=period - 1, min_periods=period).mean()
    RS = au / ad
    return pd.Series(100 - (100 / (1 + RS)), name="RSI")

def check_strategy(ticker, conditions, current_price=None):
    """
    특정 코인이 주어진 전략(조건 리스트)을 만족하는지 확인
    """
    try:
        data_cache = {} # timeframe별 데이터 캐싱
        details = [] # 지표 값 저장용 리스트
        last_price = None
        volume = 0

        for cond in conditions:
            # 데이터 가져오기
            if cond.timeframe not in data_cache:
                # 재시도 로직이 포함된 함수 사용
                data_cache[cond.timeframe] = get_ohlcv_with_retry(ticker, interval=cond.timeframe)
            
            df = data_cache[cond.timeframe]

            if df is None:
                return False, [], None, 0
            
            # 마지막 종가를 현재가로 저장 (어떤 조건에서든 한 번만 가져오면 됨)
            if last_price is None:
                last_price = df['close'].iloc[-1]
            
            # 거래대금 저장 (가장 최근에 조회된 timeframe의 거래대금 사용)
            volume = df['value'].iloc[-1]

            # 전략 계산에 필요한 최소 데이터 개수 계산 (지표 기간 + 오프셋)
            required_len = max(
                cond.left_param if cond.left_indicator != 'VAL' else 0,
                cond.right_param if cond.right_indicator != 'VAL' else 0
            ) + cond.offset + 1

            if len(df) < required_len:
                return False, [], last_price, volume
            
            # 지표 계산
            # 좌변 값 계산
            left_val = get_indicator_value(df, cond.left_indicator, cond.left_param, cond.offset)
            # 우변 값 계산
            right_val = get_indicator_value(df, cond.right_indicator, cond.right_param, cond.offset)

            if left_val is None or right_val is None:
                return False, [], last_price, volume

            # 지표 값 포맷팅 및 저장 (VAL 타입이 아닌 경우에만 기록)
            if cond.left_indicator != 'VAL':
                details.append(f"{cond.left_indicator}({cond.left_param}): {left_val:.2f}")
            if cond.right_indicator != 'VAL':
                details.append(f"{cond.right_indicator}({cond.right_param}): {right_val:.2f}")

            # 비교
            if cond.operator == 'gt':
                if not (left_val > right_val):
                    return False, [], last_price, volume
            elif cond.operator == 'lt':
                if not (left_val < right_val):
                    return False, [], last_price, volume
            elif cond.operator == 'gte':
                if not (left_val >= right_val):
                    return False, [], last_price, volume
            elif cond.operator == 'lte':
                if not (left_val <= right_val):
                    return False, [], last_price, volume
        
        return True, details, last_price, volume # 모든 조건을 통과함, 상세 정보, 현재가, 거래대금 반환

    except Exception as e:
        print(f"Error checking {ticker}: {e}")
        return False, [], None, 0

def get_indicator_value(df, indicator_type, param, offset):
    """
    DataFrame에서 특정 시점(offset)의 지표 값을 추출
    """
    target_idx = -1 - offset # -1: 현재(또는 최근 확정), -2: 1봉전
    
    if abs(target_idx) > len(df):
        return None

    if indicator_type == 'MA':
        ma = df['close'].rolling(window=param).mean()
        return ma.iloc[target_idx]
    elif indicator_type == 'RSI':
        rsi = calculate_rsi(df, period=param) # 사용자가 설정한 param(기간)을 반영
        return rsi.iloc[target_idx]
    elif indicator_type == 'VAL':
        return float(param)
    elif indicator_type == 'CLOSE':
        return float(df['close'].iloc[target_idx])
    
    return None
