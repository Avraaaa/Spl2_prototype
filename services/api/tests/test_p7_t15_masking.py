"""P7-T15 regressions from the synthetic 790-request comparison."""

import pytest

from domains.issues.services import mask_sensitive, safe_original_text

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("source", "expected", "preserved"),
    [
        (
            (
                "Pls chek acount 44012345678 which got doubel interest, the owner phone is "
                "01712345678 and the job ran on v2.4.1 under SR-1043."
            ),
            ("[ACCOUNT_NUMBER]", "[PHONE_NUMBER]"),
            ("v2.4.1", "SR-1043"),
        ),
        (
            (
                "Customer says transfer to account 1234567890123 failed with E-4012 on 12/11/2026, "
                "Txn ID 7788990011 shows pending, amount BDT 50,000."
            ),
            ("[ACCOUNT_NUMBER]",),
            ("E-4012", "12/11/2026", "Txn ID 7788990011", "BDT 50,000"),
        ),
        (
            (
                "Customer er hisab 20012345678 theke transfer korte gele Submit button kaj kore na, "
                "E-3120. Phone +8801812345678."
            ),
            ("[ACCOUNT_NUMBER]", "[PHONE_NUMBER]"),
            ("E-3120",),
        ),
        (
            (
                "গ্রাহকের হিসাব নম্বর ৩২১০৯৮৭৬৫৪৩২ থেকে ৭৫,০০০ টাকা কাটা হয়েছে, "
                "Txn ID 5566778899 ও SR-1043 দেখুন।"
            ),
            ("[ACCOUNT_NUMBER]",),
            ("Txn ID 5566778899", "SR-1043"),
        ),
        (
            ("গ্রাহকের ফোন ০১৯১২৩৪৫৬৭৮ নম্বরে ওটিপি ১২৩৪৫৬ পাঠানো হলেও কোড কাজ করেনি।"),
            ("[PHONE_NUMBER]", "[OTP REDACTED]"),
            (),
        ),
        (
            (
                "Custmer shared his card 4111111111111111 and PIN code 5821 over phone, "
                "we need to chnage the PIN, E-2210 apears."
            ),
            ("[CARD REDACTED]", "[OTP REDACTED]"),
            ("E-2210",),
        ),
        (
            "Customer er mobile 01712345678 e OTP 5521 ashche kintu app e E-1108 dekhay.",
            ("[PHONE_NUMBER]", "[OTP REDACTED]"),
            ("E-1108",),
        ),
        (
            (
                "Verification code 6642 was sent to 01512345678 but the customer's PIN 2580 "
                "was already blocked, see SR-1043."
            ),
            ("[OTP REDACTED]", "[PHONE_NUMBER]"),
            ("SR-1043",),
        ),
        (
            (
                "Beneficiary account 1100223344556 add করতে গেলে OTP 482913 আসছে না, "
                "ref SR-1043 আর v2.4.1 app এ।"
            ),
            ("[ACCOUNT_NUMBER]", "[OTP REDACTED]"),
            ("SR-1043", "v2.4.1"),
        ),
        (
            (
                "গ্রাহকের কার্ড নম্বর 4111-1111-1111-1111 দিয়ে পিন পরিবর্তন করতে গেলে "
                "E-2210 আসছে, v2.4.1 এর পর থেকে।"
            ),
            ("[CARD REDACTED]",),
            ("E-2210", "v2.4.1"),
        ),
    ],
)
def test_790_comparison_sensitive_cases(source, expected, preserved):
    masked = mask_sensitive(source)
    for marker in expected:
        assert marker in masked
    for text in preserved:
        assert text in masked
    if "1234567890123" in source:
        assert "[CARD REDACTED]" not in masked


def test_safe_original_masks_luhn_valid_card_but_preserves_references_and_dates():
    source = (
        "Card 4111-1111-1111-1111, E-1102, SR-1043, v2.4.1, 12/11/2026, "
        "BDT 50,000, Txn ID 7788990011."
    )
    masked = safe_original_text(source)
    assert "[CARD REDACTED]" in masked
    for text in ("E-1102", "SR-1043", "v2.4.1", "12/11/2026", "BDT 50,000", "Txn ID 7788990011"):
        assert text in masked


def test_non_luhn_card_length_number_is_not_redacted_as_card():
    assert "1234567890123" in mask_sensitive("Reference 1234567890123")
    assert "1234567890123" in safe_original_text("Reference 1234567890123")
