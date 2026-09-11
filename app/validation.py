import re


def is_valid_ecuadorian_id(value: str) -> bool:
    if not re.fullmatch(r"\d{10}", value):
        return False
    province = int(value[:2])
    third_digit = int(value[2])
    if not 1 <= province <= 24 or third_digit >= 6:
        return False
    total = 0
    for index, character in enumerate(value[:9]):
        digit = int(character)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    verifier = (10 - total % 10) % 10
    return verifier == int(value[-1])
