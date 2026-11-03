"""package_ethos#13: the log table's filter backend builds on cis's safe
DataTables backend, so cis.W017 no longer lists EthosLogViewSet."""
from unittest import skipUnless

from django.test import SimpleTestCase

try:
    from cis.datatables_filters import SafeDatatablesFilterBackend
except ImportError:  # myce_cis < 0.1.44a
    SafeDatatablesFilterBackend = None

from ..views.logs import EthosLogFilterBackend


@skipUnless(SafeDatatablesFilterBackend, 'needs myce_cis >= 0.1.44a')
class LogFilterBackendTests(SimpleTestCase):

    def test_builds_on_the_safe_backend(self):
        self.assertTrue(issubclass(EthosLogFilterBackend, SafeDatatablesFilterBackend))

    def test_w017_does_not_list_the_log_view(self):
        from cis.checks import datatables_backend_check
        messages = ' '.join(w.msg for w in datatables_backend_check(None))
        self.assertNotIn('EthosLogViewSet', messages)
