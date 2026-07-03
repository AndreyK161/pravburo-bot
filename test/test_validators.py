from validators import validate_phone


def test_validate_phone_accepts_plain_11_digits_starting_with_7():
    assert validate_phone("79991234567") == "+79991234567"


def test_validate_phone_accepts_leading_eight():
    assert validate_phone("89991234567") == "+79991234567"


def test_validate_phone_accepts_formatted_number():
    assert validate_phone("+7 (999) 123-45-67") == "+79991234567"


def test_validate_phone_rejects_wrong_length():
    assert validate_phone("+7999123456") is None
    assert validate_phone("+799912345678") is None


def test_validate_phone_rejects_non_phone_text():
    assert validate_phone("Иван") is None


def test_validate_phone_rejects_wrong_leading_digit():
    assert validate_phone("11234567890") is None
