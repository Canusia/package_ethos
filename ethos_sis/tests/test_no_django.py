import importlib
import pkgutil
import sys
import unittest

import ethos_sis


class NoDjangoImportTest(unittest.TestCase):
    def test_package_imports_without_django(self):
        # Simulate Django being unavailable: unconditionally block `django`
        # (and any already-imported django.* submodules) in sys.modules,
        # regardless of whether django was preloaded before this test ran.
        # Mapping a name to None in sys.modules makes `import <name>` raise
        # ImportError, which is what gives this guard teeth even when
        # nothing has imported django yet (e.g. under
        # `python -m unittest ethos_sis.tests`, where django is never
        # loaded and the old "only null out what's already present" logic
        # was a silent no-op).
        keys_to_block = {"django"} | {
            name for name in list(sys.modules) if name.startswith("django.")
        }
        saved = {k: sys.modules.get(k) for k in keys_to_block}
        sys.modules.update({k: None for k in keys_to_block})
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
