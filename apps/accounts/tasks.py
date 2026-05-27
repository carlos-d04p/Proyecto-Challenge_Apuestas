import time
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
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
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"kyc_{user_id}",
                {
                    "type": "kyc_status_update",
                    "status": "VERIFIED",
                    "message": "¡Tus datos han sido validados exitosamente! Tu cuenta está completamente activa."
                }
            )
            return f"Usuario {user_id} verificado con éxito."
            
        return f"Usuario {user_id} ya estaba en estado {perfil.status}."
        
    except PerfilKYC.DoesNotExist:
        return f"Perfil KYC no encontrado para usuario {user_id}."

@shared_task
def enviar_email_verificacion_async(user_id, token, base_url):
    """
    Simula el envío de un email asíncrono para verificar la cuenta.
    En un entorno real usaría django.core.mail.send_mail.
    """
    link = f"{base_url}/accounts/verify-email/{token}/"
    print("\n" + "="*50)
    print("SIMULADOR DE EMAIL DE FAIRBET LAB")
    print(f"Para: Usuario ID {user_id}")
    print(f"Asunto: Verifica tu cuenta")
    print(f"Por favor haz clic en el siguiente enlace para activar tu cuenta:\n{link}")
    print("="*50 + "\n")
    return f"Email simulado enviado a usuario {user_id}"
