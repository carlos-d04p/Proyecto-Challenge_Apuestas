"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/eventos/', permanent=False)),
    # Catálogo de eventos (HTML + API)
    path('eventos/', include('apps.markets.urls', namespace='markets')),
    path('api/markets/', include('apps.markets.urls', namespace='markets_api')),
    # Cuentas y autenticación
    path('api/accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('accounts/', include('apps.accounts.urls_web', namespace='accounts_web')),
    # Apuestas
    path('apuestas/', include('apps.betting.urls', namespace='betting')),
]
