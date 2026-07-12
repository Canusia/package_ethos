import unittest

from ethos_sis.accept import accept_for


class AcceptForTest(unittest.TestCase):
    def test_default_is_plain_json(self):
        self.assertEqual(accept_for("subjects"), "application/json")

    def test_known_resource_media_type(self):
        self.assertEqual(
            accept_for("sections"),
            "application/vnd.hedtech.integration.sections-maximum.v16+json",
        )
        self.assertEqual(
            accept_for("person-holds"),
            "application/vnd.hedtech.integration.v6+json",
        )

    def test_override_wins(self):
        self.assertEqual(accept_for("sections", override="application/json"),
                         "application/json")
