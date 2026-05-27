"""
Validadores para la app accounts.

- validar_dni_peruano: algoritmo de dígito verificador peruano (módulo 11)
- validar_mayoria_de_edad: verifica que el usuario tenga ≥ 18 años
"""
from datetime import date
from django.core.exceptions import ValidationError


# ── Validador de DNI peruano ──────────────────────────────────────────────────

# Tabla de conversión del dígito verificador peruano
_TABLA_VERIFICADOR = {
    0: "1", 1: "0", 2: "5", 3: "4", 4: "3",
    5: "2", 6: "1", 7: "0", 8: "9", 9: "8", 10: "7"
}

# Factores de multiplicación para los primeros 7 dígitos
_FACTORES_DNI = [3, 2, 7, 6, 5, 4, 3]


def validar_dni_peruano(dni: str) -> None:
    """
    Valida un DNI peruano mediante el algoritmo del dígito verificador.

    El DNI tiene 8 dígitos:
      - Los primeros 7 son los dígitos de datos.
      - El dígito 8 es el verificador calculado con módulo 11.

    Args:
        dni: Cadena de 8 dígitos numéricos.

    Raises:
        ValidationError: Si el DNI no es válido.
    """
    if not dni or len(dni) != 8 or not dni.isdigit():
        raise ValidationError(
            "El DNI debe contener exactamente 8 dígitos numéricos."
        )

    suma = sum(int(dni[i]) * _FACTORES_DNI[i] for i in range(7))
    residuo = suma % 11
    digito_esperado = _TABLA_VERIFICADOR.get(residuo)

    if dni[7] != digito_esperado:
        raise ValidationError(
            f"DNI inválido: el dígito verificador no coincide."
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
