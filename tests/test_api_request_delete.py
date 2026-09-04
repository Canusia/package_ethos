"""_api_request must support DELETE.

student-aptitude-assessments is the first resource we delete from; before it,
_api_request handled only GET/POST/PUT/HEAD and raised ValueError on anything
else.
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase

try:
    from ethos.ethos.library.base import EthosBase
    from ethos.ethos.models import EthosLog
except ImportError:
    from ethos.library.base import EthosBase
    from ethos.models import EthosLog


class ApiRequestDeleteTest(TestCase):

    def setUp(self):
        self.client_obj = EthosBase.__new__(EthosBase)
        self.client_obj.URL = 'https://integrate.elluciancloud.com'

    @patch('requests.delete')
    @patch.object(EthosBase, 'get_auth_token', return_value='fake-token')
    def test_delete_issues_a_delete_request(self, mock_token, mock_delete):
        resp = MagicMock(status_code=204, text='')
        mock_delete.return_value = resp

        result, log = self.client_obj._api_request(
            'DELETE', 'https://example.test/api/thing/abc', 'thing_delete')

        self.assertIs(result, resp)
        mock_delete.assert_called_once()
        self.assertEqual(mock_delete.call_args[0][0],
                         'https://example.test/api/thing/abc')

    @patch('requests.delete')
    @patch.object(EthosBase, 'get_auth_token', return_value='fake-token')
    def test_delete_is_logged(self, mock_token, mock_delete):
        mock_delete.return_value = MagicMock(status_code=204, text='')

        self.client_obj._api_request(
            'DELETE', 'https://example.test/api/thing/abc', 'thing_delete')

        log = EthosLog.objects.latest('id')
        self.assertEqual(log.method, 'DELETE')
        self.assertEqual(log.response_status, 204)
