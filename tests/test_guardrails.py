from src.core.guardrails import check_input


def test_blocks_toxic_tagalog():
    passed, reason = check_input("putangina mo yan")
    assert not passed
    assert "putangina" in reason


def test_blocks_toxic_english():
    passed, reason = check_input("fuck you gago")
    assert not passed


def test_blocks_pii_email():
    passed, reason = check_input("email ko ay test@example.com")
    assert not passed
    assert "email" in reason


def test_blocks_pii_phone():
    passed, reason = check_input("tawagan mo ko 0917-123-4567")
    assert not passed
    assert "PH mobile" in reason


def test_blocks_pii_credit_card():
    passed, reason = check_input("card number 4111-1111-1111-1111")
    assert not passed
    assert "credit card" in reason


def test_allows_normal_tagalog():
    passed, _ = check_input("Gusto ko maging nurse sa ospital")
    assert passed


def test_allows_normal_english():
    passed, _ = check_input("I want to become a software engineer")
    assert passed


def test_allows_normal_taglish():
    passed, _ = check_input("Gusto ko ng career sa tech, like programming")
    assert passed
