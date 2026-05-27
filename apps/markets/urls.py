from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, MarketViewSet, SelectionViewSet
from .views_web import event_list, event_detail

app_name = "markets"

# ── API REST ──────────────────────────────────────────────────────────────────
router = DefaultRouter()
router.register(r"events",     EventViewSet,    basename="event")
router.register(r"markets",    MarketViewSet,   basename="market")
router.register(r"selections", SelectionViewSet, basename="selection")

# ── Vistas web (HTML) ─────────────────────────────────────────────────────────
web_urlpatterns = [
    path("",           event_list,   name="event_list"),
    path("<uuid:pk>/", event_detail, name="event_detail"),
]

urlpatterns = web_urlpatterns + router.urls

