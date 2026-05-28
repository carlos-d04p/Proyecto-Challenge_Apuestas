"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.wallet.views import WalletPageView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('backoffice/', include('apps.backoffice.urls', namespace='backoffice')),
    path('wallet/', WalletPageView.as_view(), name='wallet-dashboard'),
    path('api/wallet/', include('apps.wallet.urls')),
    path('', RedirectView.as_view(url='/eventos/', permanent=False), name='home'),
    # Catalogo de eventos (HTML + API)
    path('eventos/', include('apps.markets.urls', namespace='markets')),
    path('api/markets/', include('apps.markets.urls', namespace='markets_api')),
    # Cuentas y autenticacion
    path('api/accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('accounts/', include('apps.accounts.urls_web', namespace='accounts_web')),
    # Apuestas
    path('apuestas/', include('apps.betting.urls', namespace='betting')),
]
