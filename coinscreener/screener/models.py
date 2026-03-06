from django.db import models

class Strategy(models.Model):
    name = models.CharField(max_length=100, verbose_name="전략명")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Condition(models.Model):
    TIMEFRAME_CHOICES = [
        ('minute1', '1분봉'),
        ('minute3', '3분봉'),
        ('minute5', '5분봉'),
        ('minute10', '10분봉'),
        ('minute15', '15분봉'),
        ('minute30', '30분봉'),
        ('minute60', '1시간봉'),
        ('minute240', '4시간봉'),
        ('day', '일봉'),
        ('week', '주봉'),
        ('month', '월봉'),
    ]
    
    INDICATOR_CHOICES = [
        ('MA', '이동평균(MA)'),
        ('RSI', 'RSI'),
        ('VAL', '고정값'), # 비교 대상이 숫자인 경우
        ('CLOSE', '종가'),
    ]

    OPERATOR_CHOICES = [
        ('gt', '크다 (>)'),
        ('lt', '작다 (<)'),
        ('gte', '이상 (>=)'),
        ('lte', '이하 (<=)'),
    ]

    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, related_name='conditions')
    
    # 공통 조건
    timeframe = models.CharField(max_length=20, choices=TIMEFRAME_CHOICES, default='day')
    offset = models.IntegerField(default=0, verbose_name="n봉 전") # 0이면 현재봉, 1이면 전봉

    # 좌변 (예: 5MA)
    left_indicator = models.CharField(max_length=10, choices=INDICATOR_CHOICES, default='MA')
    left_param = models.IntegerField(default=5, verbose_name="좌변 기간/값") # MA일 경우 기간, RSI일 경우 기간

    # 비교 연산자
    operator = models.CharField(max_length=5, choices=OPERATOR_CHOICES, default='gt')

    # 우변 (예: 10MA 또는 30)
    right_indicator = models.CharField(max_length=10, choices=INDICATOR_CHOICES, default='MA')
    right_param = models.IntegerField(default=20, verbose_name="우변 기간/값")

    def __str__(self):
        return f"{self.offset}봉전 {self.left_indicator}({self.left_param}) {self.operator} {self.right_indicator}({self.right_param})"
