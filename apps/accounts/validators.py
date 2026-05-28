"""
Validadores para la app accounts.

- validar_dni_peruano: algoritmo de dígito verificador peruano (módulo 11)
- validar_mayoria_de_edad: verifica que el usuario tenga ≥ 18 años
"""
from datetime import date
from django.core.exceptions import ValidationError


# ── Validador de DNI peruano ──────────────────────────────────────────────────

# Tabla de conversión del dígito verificador peruano
def validar_dni_peruano(dni: str, verificador: str) -> None:
    """
    Valida un DNI peruano mediante el algoritmo del dígito verificador.

    Args:
        dni: Cadena de 8 dígitos numéricos.
        verificador: El dígito verificador (usualmente 1 caracter numérico o letra).

    Raises:
        ValidationError: Si el DNI no es válido.
    """
    if not dni or len(dni) != 8 or not dni.isdigit():
        raise ValidationError(
            "El DNI debe contener exactamente 8 dígitos numéricos."
        )

    factores = [3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(dni[i]) * factores[i] for i in range(8))
    residuo = suma % 11
    
    # Tabla estándar usada comúnmente para validar
    tabla = [6, 5, 4, 3, 2, 1, 1, 0, 9, 8, 7]
    digito_esperado = str(tabla[residuo])

    if str(verificador).upper() != digito_esperado:
        raise ValidationError(
            "DNI inválido: el dígito verificador no coincide con tu número de DNI."
        )


# ── Validador de mayoría de edad ──────────────────────────────────────────────

EDAD_MINIMA = 18


def validar_mayoria_de_edad(birth_date: date) -> None:
    """
    Valida que el usuario tenga al menos 18 años de edad.

    Args:
        birth_date: Fecha de nacimiento del usuario.

    Raises:
        ValidationError: Si el usuario es menor de 18 años.
    """
    today = date.today()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    if age < EDAD_MINIMA:
        raise ValidationError(
            f"Debes tener al menos {EDAD_MINIMA} años para registrarte "
            f"en FairBet Lab. Edad detectada: {age} años."
        )
