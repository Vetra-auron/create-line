import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure the parent directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from committee.member import CommitteeMember
from committee.chairperson import Chairperson

class TestCommitteeMember(unittest.TestCase):

    @patch.dict(os.environ, {}, clear=True)
    def test_mock_response_no_key(self):
        """Test that analyze returns mock response when no API key is present."""
        member = CommitteeMember("Bob", "Tester", "Test Persona")
        # Ensure client is None
        member.client = None

        response = member.analyze("Test Content")
        self.assertIn("MOCK", response)
        self.assertIn("Bob", response)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"})
    def test_api_call_mocked(self):
        """Test that analyze calls the API when key is present (mocked)."""
        with patch("committee.member.OpenAI") as MockOpenAI:
            # Setup mock
            mock_client = MagicMock()
            mock_completion = MagicMock()
            mock_completion.choices[0].message.content = "API Analysis Result"
            mock_client.chat.completions.create.return_value = mock_completion
            MockOpenAI.return_value = mock_client

            member = CommitteeMember("Charlie", "APIRole", "API Persona")

            # Verify client is set
            self.assertIsNotNone(member.client)

            response = member.analyze("API Content")

            self.assertEqual(response, "API Analysis Result")
            mock_client.chat.completions.create.assert_called_once()

class TestChairperson(unittest.TestCase):

    def test_add_member(self):
        chair = Chairperson()
        member = MagicMock()
        chair.add_member(member)
        self.assertIn(member, chair.members)

    def test_convene(self):
        chair = Chairperson()

        # Create mock members
        m1 = MagicMock()
        m1.name = "M1"
        m1.role = "R1"
        m1.analyze.return_value = "Result 1"

        m2 = MagicMock()
        m2.name = "M2"
        m2.role = "R2"
        m2.analyze.return_value = "Result 2"

        chair.add_member(m1)
        chair.add_member(m2)

        results = chair.convene("Test Content")

        self.assertEqual(results["M1"], "Result 1")
        self.assertEqual(results["M2"], "Result 2")
        m1.analyze.assert_called_with("Test Content")
        m2.analyze.assert_called_with("Test Content")

    def test_synthesize(self):
        chair = Chairperson()
        results = {
            "Member A": "Analysis A",
            "Member B": "Analysis B"
        }
        report = chair.synthesize(results)

        self.assertIn("Member A's Feedback", report)
        self.assertIn("Analysis A", report)
        self.assertIn("Member B's Feedback", report)
        self.assertIn("Analysis B", report)

if __name__ == "__main__":
    unittest.main()
