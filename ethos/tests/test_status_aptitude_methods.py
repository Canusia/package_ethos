"""API Explorer coverage for the aptitude-assessment methods.

Also pins two invariants of the method runner that the write methods depend on:
every registered name must exist on the Ethos client, and structured params
(arrays/objects) must reach the method as Python values rather than strings.
"""
import importlib.util
import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

if importlib.util.find_spec('ethos.ethos'):
    from ethos.ethos.library.ethos import Ethos
    from ethos.ethos.views import status as status_views
else:
    from ethos.library.ethos import Ethos
    from ethos.views import status as status_views


APTITUDE_METHODS = [
    'get_aptitude_assessments',
    'get_aptitude_assessment_by_id',
    'get_student_aptitude_assessments',
    'get_student_aptitude_assessment',
    'get_student_scores_resolved',
    'create_student_aptitude_assessment',
    'update_student_aptitude_assessment',
    'delete_student_aptitude_assessment',
]


class MethodRegistryTest(TestCase):

    def test_aptitude_methods_are_registered(self):
        for name in APTITUDE_METHODS:
            with self.subTest(method=name):
                self.assertIn(name, status_views._ALLOWED_METHODS)

    def test_every_registered_method_exists_on_the_client(self):
        for name in status_views._ALLOWED_METHODS:
            with self.subTest(method=name):
                self.assertTrue(hasattr(Ethos, name),
                                f'{name} is registered but not on Ethos')

    def test_both_aptitude_groups_are_present(self):
        self.assertIn('aptitude_assessments', status_views.METHOD_REGISTRY)
        self.assertIn('student_aptitude_assessments', status_views.METHOD_REGISTRY)


class RunMethodJsonParamsTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def _run(self, method_name, params):
        request = self.factory.post(
            '/ce/ethos/status/run/',
            data=json.dumps({'method_name': method_name, 'params': params}),
            content_type='application/json')
        return status_views.run_method(request)

    @patch.object(status_views, 'Ethos')
    def test_percentiles_arrive_as_a_list(self, mock_ethos_cls):
        client = MagicMock()
        client.create_student_aptitude_assessment.return_value = {'id': 'x'}
        mock_ethos_cls.return_value = client

        self._run('create_student_aptitude_assessment', {
            'student_id': 'S-GUID',
            'assessment_id': 'A-GUID',
            'assessed_on': '2025-10-04',
            'score_value': '27',
            'percentiles': '[{"value": 88, "type": {"id": "P-GUID"}}]',
        })

        kwargs = client.create_student_aptitude_assessment.call_args[1]
        self.assertEqual(kwargs['percentiles'],
                         [{'value': 88, 'type': {'id': 'P-GUID'}}])

    @patch.object(status_views, 'Ethos')
    def test_payload_arrives_as_a_dict(self, mock_ethos_cls):
        client = MagicMock()
        client.update_student_aptitude_assessment.return_value = {'id': 'x'}
        mock_ethos_cls.return_value = client

        self._run('update_student_aptitude_assessment', {
            'record_id': 'R-GUID',
            'payload': '{"assessedOn": "2025-10-04"}',
        })

        kwargs = client.update_student_aptitude_assessment.call_args[1]
        self.assertEqual(kwargs['payload'], {'assessedOn': '2025-10-04'})

    @patch.object(status_views, 'Ethos')
    def test_malformed_json_param_is_a_400_not_a_500(self, mock_ethos_cls):
        mock_ethos_cls.return_value = MagicMock()

        response = self._run('update_student_aptitude_assessment', {
            'record_id': 'R-GUID',
            'payload': '{not json',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('payload', json.loads(response.content)['error'])
