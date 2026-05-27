"""
Tests del validador de DNI peruano y mayoría de edad.
"""
import pytest
from datetime import date, timedelta
from django.core.exceptions import ValidationError

from apps.accounts.validators import validar_dni_peruano, validar_mayoria_de_edad


class TestValidadorDNI:
    """Tests del algoritmo del dígito verificador peruano."""

    def test_dni_valido_ejemplo_1(self):
        """Un DNI con dígito verificador correcto no lanza excepción."""
        # DNI de ejemplo: primeros 7 = 1234567, verificador calculado = ?
        # Suma: 1*3 + 2*2 + 3*7 + 4*6 + 5*5 + 6*4 + 7*3 = 3+4+21+24+25+24+21 = 122
        # 122 % 11 = 1 → tabla[1] = '0'
        validar_dni_peruano("12345670")

    def test_dni_valido_ejemplo_2(self):
        """Otro DNI válido no lanza excepción."""
        # 4 5 6 7 8 9 0 ?
        # 4*3 + 5*2 + 6*7 + 7*6 + 8*5 + 9*4 + 0*3 = 12+10+42+42+40+36+0 = 182
        # 182 % 11 = 6 → tabla[6] = '1'
        validar_dni_peruano("45678901")

    def test_dni_invalido_digito_verificador(self):
        """DNI con dígito verificador incorrecto lanza ValidationError."""
        with pytest.raises(ValidationError, match="dígito verificador"):
            validar_dni_peruano("12345679")  # verificador correcto sería '0'

    def test_dni_longitud_incorrecta(self):
        """DNI con menos de 8 dígitos lanza ValidationError."""
        with pytest.raises(ValidationError):
            validar_dni_peruano("1234567")

    def test_dni_con_letras(self):
        """DNI con letras lanza ValidationError."""
        with pytest.raises(ValidationError):
            validar_dni_peruano("1234ABCD")

    def test_dni_vacio(self):
        """DNI vacío lanza ValidationError."""
        with pytest.raises(ValidationError):
            validar_dni_peruano("")

    def test_dni_con_espacios(self):
        """DNI con espacios lanza ValidationError."""
        with pytest.raises(ValidationError):
            validar_dni_peruano("1234 678")

    def test_dni_9_digitos(self):
        """DNI con 9 dígitos lanza ValidationError."""
        with pytest.raises(ValidationError):
            validar_dni_peruano("123456789")


class TestValidadorMayoriaDeEdad:
    """Tests de validación de mayoría de edad (≥ 18 años)."""

    def test_mayor_de_18_exacto(self):
        """Un usuario que cumplió exactamente 18 hoy puede registrarse."""
        hoy = date.today()
        cumple_18_hoy = date(hoy.year - 18, hoy.month, hoy.day)
        validar_mayoria_de_edad(cumple_18_hoy)  # No debe lanzar excepción

    def test_mayor_de_18_adulto(self):
        """Un adulto de 25 años puede registrarse sin problemas."""
        nacimiento = date.today() - timedelta(days=365 * 25)
        validar_mayoria_de_edad(nacimiento)

    def test_menor_de_18_lanza_error(self):
        """Un menor de 18 años no puede registrarse."""
        menor = date.today() - timedelta(days=365 * 17)
        with pytest.raises(ValidationError, match="18 años"):
            validar_mayoria_de_edad(menor)

    def test_recien_nacido_lanza_error(self):
        """Un bebé recién nacido no puede registrarse."""
        with pytest.raises(ValidationError):
            validar_mayoria_de_edad(date.today())

    def test_17_anos_11_meses_lanza_error(self):
        """17 años y 11 meses no es suficiente."""
        casi_18 = date.today() - timedelta(days=365 * 18 - 1)
        with pytest.raises(ValidationError):
            validar_mayoria_de_edad(casi_18)
