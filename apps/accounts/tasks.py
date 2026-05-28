import time
try:
    from celery import shared_task
except ModuleNotFoundError:
    def shared_task(func):
        func.delay = func
        func.apply_async = lambda args=None, kwargs=None, **_options: func(
            *(args or ()),
            **(kwargs or {}),
        )
        return func

from django.utils import timezone
from django.core.mail import send_mail
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import PerfilKYC, CustomUser

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
    Envía un email asíncrono para verificar la cuenta usando Mailpit.
    """
    try:
        user = CustomUser.objects.get(id=user_id)
        email_destino = user.email if user.email else "usuario@test.com"
        
        link = f"{base_url}/accounts/verify-email/{token}/"
        asunto = "FairBet Lab - Verifica tu cuenta"
        mensaje = f"Hola {user.username},\n\nPor favor haz clic en el siguiente enlace para activar tu cuenta e iniciar el proceso de verificación KYC:\n\n{link}\n\nGracias,\nEquipo FairBet Lab."
        
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email="no-reply@fairbetlab.com",
            recipient_list=[email_destino],
            fail_silently=False,
        )
        return f"Email real enviado a {email_destino} para usuario {user_id}"
    except CustomUser.DoesNotExist:
        return f"Error: Usuario {user_id} no existe."
