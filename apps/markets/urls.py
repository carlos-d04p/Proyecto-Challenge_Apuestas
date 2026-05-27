from rest_framework.routers import DefaultRouter
from .views import EventViewSet, MarketViewSet, SelectionViewSet

router = DefaultRouter()
router.register(r"events", EventViewSet, basename="event")
router.register(r"markets", MarketViewSet, basename="market")
router.register(r"selections", SelectionViewSet, basename="selection")

urlpatterns = router.urls
