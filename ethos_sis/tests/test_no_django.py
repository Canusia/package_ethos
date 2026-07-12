import importlib
import pkgutil
import sys
import unittest

import ethos_sis


class NoDjangoImportTest(unittest.TestCase):
    def test_package_imports_without_django(self):
        # Simulate Django being unavailable: block it in sys.modules.
        blocked = {name: None for name in list(sys.modules) if name == "django"
                   or name.startswith("django.")}
        saved = {k: sys.modules.get(k) for k in blocked}
        sys.modules.update(blocked)  # importing django now raises ImportError
        try:
            for mod in pkgutil.walk_packages(ethos_sis.__path__,
                                             prefix="ethos_sis."):
                if ".tests" in mod.name:
                    continue
                importlib.reload(importlib.import_module(mod.name))
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    def test_no_source_references_django_or_cis(self):
        import os
        root = os.path.dirname(ethos_sis.__file__)
        offenders = []
        for dirpath, _dirs, files in os.walk(root):
            if os.path.basename(dirpath) == "tests":
                continue
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                with open(path) as fh:
                    text = fh.read()
                if "import django" in text or "from django" in text \
                        or "import cis" in text or "from cis" in text:
                    offenders.append(path)
        self.assertEqual(offenders, [], f"Django/cis imports found: {offenders}")
