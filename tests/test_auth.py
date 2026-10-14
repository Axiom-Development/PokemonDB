import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth


class TestAuth(unittest.TestCase):
    def test_hash_is_salted_and_not_plaintext(self):
        salt_hex, hash_hex = auth.hash_password("correct-horse")
        self.assertNotEqual(hash_hex, "correct-horse")
        self.assertNotIn("correct-horse", hash_hex)
        self.assertEqual(len(salt_hex), auth.SALT_BYTES * 2)

    def test_same_password_different_salts_different_hashes(self):
        salt1, hash1 = auth.hash_password("correct-horse")
        salt2, hash2 = auth.hash_password("correct-horse")
        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(hash1, hash2)

    def test_verify_correct_password(self):
        salt_hex, hash_hex = auth.hash_password("correct-horse")
        self.assertTrue(auth.verify_password("correct-horse", salt_hex, hash_hex))

    def test_verify_wrong_password(self):
        salt_hex, hash_hex = auth.hash_password("correct-horse")
        self.assertFalse(auth.verify_password("wrong-password", salt_hex, hash_hex))

    def test_session_tokens_unique(self):
        tokens = {auth.new_session_token() for _ in range(50)}
        self.assertEqual(len(tokens), 50)

    def test_username_validation(self):
        self.assertIsNone(auth.validate_username("ash_ketchum"))
        self.assertIsNotNone(auth.validate_username("ab"))  # too short
        self.assertIsNotNone(auth.validate_username("has space"))
        self.assertIsNotNone(auth.validate_username("a" * 30))  # too long

    def test_password_validation(self):
        self.assertIsNone(auth.validate_password("longenough"))
        self.assertIsNotNone(auth.validate_password("short"))


if __name__ == "__main__":
    unittest.main()
