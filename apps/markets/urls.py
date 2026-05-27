from django.urls import path
from django.http import HttpResponse

app_name = 'markets'

def dummy_view(request):
    return HttpResponse("Eventos (Stub para rama Walter_Llatas)")

urlpatterns = [
    path('', dummy_view, name='event_list'),
    path('events/', dummy_view, name='events-list'),
]
