import time
from celery import shared_task
from django.utils import timezone
from .models import PerfilKYC

@shared_task
def verificar_kyc_async(user_id):
    """
    Simula la verificación de KYC asincrónica.
    Toma 5 segundos (simulando API RENIEC) y luego cambia el estado a VERIFIED.
    """
    # Simulamos el tiempo de espera de una API externa (5 segundos)
    time.sleep(5)
    
    try:
        perfil = PerfilKYC.objects.get(user_id=user_id)
        
        # Solo verificamos si está en estado PENDING
        if perfil.status == PerfilKYC.Status.PENDING:
            perfil.status = PerfilKYC.Status.VERIFIED
            perfil.verified_at = timezone.now()
            perfil.save()
            return f"Usuario {user_id} verificado con éxito."
            
        return f"Usuario {user_id} ya estaba en estado {perfil.status}."
        
    except PerfilKYC.DoesNotExist:
        return f"Perfil KYC no encontrado para usuario {user_id}."
