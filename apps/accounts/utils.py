from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

def generar_token_email(user_id):
    """Genera un token firmado criptográficamente para verificar el email."""
    signer = TimestampSigner()
    return signer.sign(str(user_id))

def verificar_token_email(token, max_age=86400):
    """
    Verifica el token y retorna el user_id si es válido.
    max_age: 86400 segundos = 24 horas.
    """
    signer = TimestampSigner()
    try:
        user_id = signer.unsign(token, max_age=max_age)
        return user_id
    except (BadSignature, SignatureExpired):
        return None

from django.core.cache import cache
from .models import CustomUser, PerfilKYC

def check_and_increment_login_fails(username):
    """
    Incrementa el contador de fallos de login en Redis.
    Si llega a 5, bloquea la cuenta.
    Retorna True si la cuenta acaba de ser bloqueada.
    """
    cache_key = f"login_fails_{username}"
    fails = cache.get(cache_key, 0)
    fails += 1
    
    if fails >= 5:
        try:
            user = CustomUser.objects.get(username=username)
            if hasattr(user, 'perfil_kyc') and user.perfil_kyc.status != PerfilKYC.Status.BLOCKED:
                user.perfil_kyc.status = PerfilKYC.Status.BLOCKED
                user.perfil_kyc.save()
            cache.delete(cache_key)
            return True
        except CustomUser.DoesNotExist:
            pass
    
    # Expiración de 1 hora para los intentos
    cache.set(cache_key, fails, timeout=3600)
    return False

def reset_login_fails(username):
    """Resetea el contador de fallos de login tras un login exitoso."""
    cache_key = f"login_fails_{username}"
    cache.delete(cache_key)
