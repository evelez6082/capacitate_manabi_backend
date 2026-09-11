import unittest

from app.anti_automation import (
    InvalidFormChallenge,
    issue_form_challenge,
    private_fingerprint,
    verify_form_challenge,
)


class AntiAutomationTests(unittest.TestCase):
    secret = "a-secure-test-secret-with-more-than-32-characters"

    def test_challenge_is_valid_only_inside_allowed_time_window(self) -> None:
        token = issue_form_challenge(self.secret, now=1_000)
        challenge = verify_form_challenge(token, self.secret, 3, 1_800, now=1_004)
        self.assertEqual(challenge["iat"], 1_000)

        with self.assertRaises(InvalidFormChallenge):
            verify_form_challenge(token, self.secret, 3, 1_800, now=1_001)
        with self.assertRaises(InvalidFormChallenge):
            verify_form_challenge(token, self.secret, 3, 1_800, now=2_801)

    def test_tampered_challenge_is_rejected(self) -> None:
        token = issue_form_challenge(self.secret, now=1_000)
        with self.assertRaises(InvalidFormChallenge):
            verify_form_challenge(f"{token}x", self.secret, 3, 1_800, now=1_004)

    def test_fingerprints_are_private_and_stable(self) -> None:
        first = private_fingerprint(" User@Example.com ", self.secret)
        second = private_fingerprint("user@example.com", self.secret)
        self.assertEqual(first, second)
        self.assertNotIn("user@example.com", first)


if __name__ == "__main__":
    unittest.main()
