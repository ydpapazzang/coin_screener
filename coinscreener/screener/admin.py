from django.contrib import admin
from .models import Strategy, Condition

class ConditionInline(admin.TabularInline):
    model = Condition
    extra = 1

@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    inlines = [ConditionInline]

@admin.register(Condition)
class ConditionAdmin(admin.ModelAdmin):
    list_display = ('strategy', 'timeframe', 'offset', 'left_indicator', 'operator', 'right_indicator')
