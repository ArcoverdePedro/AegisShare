import re

from django.core.exceptions import ValidationError


def normalize_cpf(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def validate_cpf(value: str) -> None:
    cpf = normalize_cpf(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError("CPF inválido.")

    numbers = [int(char) for char in cpf]
    first = (sum(numbers[index] * (10 - index) for index in range(9)) * 10) % 11
    first = 0 if first == 10 else first
    second = (sum(numbers[index] * (11 - index) for index in range(10)) * 10) % 11
    second = 0 if second == 10 else second

    if numbers[9] != first or numbers[10] != second:
        raise ValidationError("CPF inválido.")
