from django.shortcuts import render, redirect, get_object_or_404
from .models import Strategy, Condition
from .engine import check_strategy
import pyupbit
import concurrent.futures
import time
from django.utils import timezone
from django.contrib import messages
from django.core.cache import cache

# 1. 전략 리스트 화면
def strategy_list(request):
    strategies = Strategy.objects.all().order_by('-created_at')
    return render(request, 'screener/strategy_list.html', {'strategies': strategies})

def strategy_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        strategy = Strategy.objects.create(name=name)
        return redirect('strategy_detail', strategy_id=strategy.id)
    return redirect('strategy_list')

def strategy_delete(request):
    if request.method == 'POST':
        strategy_ids = request.POST.getlist('strategy_ids')
        for s_id in strategy_ids:
            cache.delete(f"strategy_results_{s_id}")
        Strategy.objects.filter(id__in=strategy_ids).delete()
    return redirect('strategy_list')

# 2. 전략 상세 화면 (조건 관리)
def strategy_detail(request, strategy_id):
    strategy = get_object_or_404(Strategy, id=strategy_id)
    conditions = strategy.conditions.all()
    
    return render(request, 'screener/strategy_detail.html', {
        'strategy': strategy,
        'conditions': conditions
    })

def condition_add(request, strategy_id):
    strategy = get_object_or_404(Strategy, id=strategy_id)
    if request.method == 'POST':
        cond_type = request.POST.get('cond_type')
        timeframe = request.POST.get('timeframe')
        offset = int(request.POST.get('offset', 0))
        operator = request.POST.get('operator')

        # 공통 검증: n봉 전 (offset)
        if offset < 0:
            messages.error(request, "n봉 전은 0 이상의 숫자여야 합니다.")
            return redirect('strategy_detail', strategy_id=strategy_id)

        if cond_type == 'MA':
            price_a_type = request.POST.get('ma_price_a_type')
            ma_a_val = int(request.POST.get('ma_price_a_val', 5))
            ma_b_val = int(request.POST.get('ma_price_b_val', 20))

            if price_a_type == 'CLOSE':
                left_indicator, left_param = 'CLOSE', 0
            else:
                if ma_a_val < 1:
                    messages.error(request, "이동평균 기간은 1 이상이어야 합니다.")
                    return redirect('strategy_detail', strategy_id=strategy_id)
                left_indicator, left_param = 'MA', ma_a_val
            
            if ma_b_val < 1:
                messages.error(request, "이동평균 기간은 1 이상이어야 합니다.")
                return redirect('strategy_detail', strategy_id=strategy_id)
            right_indicator, right_param = 'MA', ma_b_val
        
        elif cond_type == 'RSI':
            rsi_period = int(request.POST.get('rsi_period', 14))
            rsi_threshold = int(request.POST.get('rsi_threshold', 30))

            if rsi_period < 1:
                messages.error(request, "RSI 기간은 1 이상이어야 합니다.")
                return redirect('strategy_detail', strategy_id=strategy_id)
            if not (0 <= rsi_threshold <= 100):
                messages.error(request, "RSI 기준값은 0에서 100 사이여야 합니다.")
                return redirect('strategy_detail', strategy_id=strategy_id)

            left_indicator, left_param = 'RSI', rsi_period
            right_indicator, right_param = 'VAL', rsi_threshold

        Condition.objects.create(
            strategy=strategy,
            timeframe=timeframe,
            offset=offset,
            left_indicator=left_indicator,
            left_param=left_param,
            operator=operator,
            right_indicator=right_indicator,
            right_param=right_param,
        )
        # 조건이 변경되면 기존 검색 결과 캐시 삭제
        cache.delete(f"strategy_results_{strategy_id}")
    return redirect('strategy_detail', strategy_id=strategy_id)

def condition_delete(request, strategy_id, condition_id):
    condition = get_object_or_404(Condition, id=condition_id)
    condition.delete()
    # 조건이 삭제되면 기존 검색 결과 캐시 삭제
    cache.delete(f"strategy_results_{strategy_id}")
    return redirect('strategy_detail', strategy_id=strategy_id)

# 3. 코인 조회 화면 (검색 결과)
def coin_search(request, strategy_id):
    strategy = get_object_or_404(Strategy, id=strategy_id)
    
    # 캐시 확인: 동일한 전략에 대해 최근 검색 결과가 있으면 즉시 반환
    # URL에 ?refresh=1 이 포함된 경우 캐시를 무시하고 새로 고침
    cache_key = f"strategy_results_{strategy_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data and request.GET.get('refresh') != '1':
        return render(request, 'screener/coin_list.html', {
            'results': cached_data['results'],
            'strategy': strategy,
            'rate_limit_warning': cached_data['rate_limit_warning'],
            'is_cached': True,
            'last_updated': cached_data.get('last_updated')
        })

    # 스레드에서 DB 접근을 피하기 위해 미리 리스트로 변환
    conditions = list(strategy.conditions.all())
    
    # KRW 마켓의 모든 티커 가져오기
    tickers = pyupbit.get_tickers(fiat="KRW")
    results = []

    def process_ticker(ticker):
        try:
            is_match, details, price, volume = check_strategy(ticker, conditions)
            if price is None:
                # API 호출 실패를 나타내는 특수 신호 반환
                return "API_ERROR"
            if is_match:
                # 중복 제거 (예: 여러 조건에서 MA(5)를 쓰면 한 번만 표시)
                unique_details = list(dict.fromkeys(details))
                return {
                    'symbol': ticker,
                    'price': price, # engine에서 가져온 가격 재사용 (통신 절약)
                    'details': ", ".join(unique_details),
                    'volume': volume,
                    'volume_display': f"{volume / 100000000:.1f}억" # 억 단위 표시
                }
        except Exception:
            pass
        return None

    # max_workers를 너무 높이면 초당 호출 제한에 걸릴 수 있으므로 5~10 사이 권장
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_ticker = {executor.submit(process_ticker, t): t for t in tickers}
        
        error_occurred = False
        for future in concurrent.futures.as_completed(future_to_ticker):
            result = future.result()
            if result == "API_ERROR":
                error_occurred = True
            elif result:
                results.append(result)
            
    # 거래대금(volume) 기준 내림차순 정렬
    results.sort(key=lambda x: x.get('volume', 0), reverse=True)

    last_updated = timezone.now()

    # 검색 결과를 캐시에 저장 (5분간 유효)
    cache.set(cache_key, {
        'results': results,
        'rate_limit_warning': error_occurred,
        'last_updated': last_updated
    }, timeout=300)

    return render(request, 'screener/coin_list.html', {
        'results': results, 
        'strategy': strategy,
        'rate_limit_warning': error_occurred,
        'last_updated': last_updated
    })
