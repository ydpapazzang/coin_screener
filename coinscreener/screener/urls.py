from django.urls import path
from . import views

urlpatterns = [
    path('', views.strategy_list, name='strategy_list'),
    path('create/', views.strategy_create, name='strategy_create'),
    path('delete/', views.strategy_delete, name='strategy_delete'),
    
    path('strategy/<int:strategy_id>/', views.strategy_detail, name='strategy_detail'),
    path('strategy/<int:strategy_id>/search/', views.coin_search, name='coin_search'),
    
    path('strategy/<int:strategy_id>/condition/add/', views.condition_add, name='condition_add'),
    path('strategy/<int:strategy_id>/condition/<int:condition_id>/delete/', views.condition_delete, name='condition_delete'),
]
