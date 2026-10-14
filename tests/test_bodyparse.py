import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import bodyparse


class TestParseContentLength(unittest.TestCase):
    def test_missing_header_means_no_body(self):
        self.assertEqual(bodyparse.parse_content_length(None), 0)

    def test_valid_numeric_header(self):
        self.assertEqual(bodyparse.parse_content_length("42"), 42)

    def test_negative_length_rejected(self):
        self.assertIsNone(bodyparse.parse_content_length("-1"))

    def test_non_numeric_header_rejected(self):
        self.assertIsNone(bodyparse.parse_content_length("not-a-number"))

    def test_oversized_length_rejected(self):
        self.assertIsNone(bodyparse.parse_content_length(str(bodyparse.MAX_BODY_BYTES + 1)))

    def test_exactly_max_bytes_allowed(self):
        self.assertEqual(bodyparse.parse_content_length(str(bodyparse.MAX_BODY_BYTES)), bodyparse.MAX_BODY_BYTES)


class TestParseJsonObject(unittest.TestCase):
    def test_empty_bytes_is_empty_object(self):
        self.assertEqual(bodyparse.parse_json_object(b""), {})

    def test_valid_object(self):
        self.assertEqual(bodyparse.parse_json_object(b'{"username": "ash"}'), {"username": "ash"})

    def test_rejects_bare_array(self):
        self.assertIsNone(bodyparse.parse_json_object(b"[1, 2, 3]"))

    def test_rejects_bare_string(self):
        self.assertIsNone(bodyparse.parse_json_object(b'"hello"'))

    def test_rejects_bare_number(self):
        self.assertIsNone(bodyparse.parse_json_object(b"42"))

    def test_rejects_null(self):
        self.assertIsNone(bodyparse.parse_json_object(b"null"))

    def test_rejects_invalid_json_syntax(self):
        self.assertIsNone(bodyparse.parse_json_object(b"{not valid json"))

    def test_rejects_invalid_utf8(self):
        self.assertIsNone(bodyparse.parse_json_object(b"\xff\xfe\x00\x01"))


if __name__ == "__main__":
    unittest.main()
