"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from apps.betting import views as betting_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('backoffice/', include('apps.backoffice.urls')),
    path('api/wallet/', include('apps.wallet.urls')),
    path('api/accounts/', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),
    path('accounts/', include(('apps.accounts.urls_web', 'accounts_web'), namespace='accounts_web')),
    path('api/markets/', include(('apps.markets.urls', 'markets'), namespace='markets_api')),
    path('markets/', include(('apps.markets.urls', 'markets'), namespace='markets')),
    path('betting/', include(('apps.betting.urls', 'betting'), namespace='betting')),
    path('', betting_views.dashboard, name='dashboard'),
]


