from importlib import import_module

from django.conf import settings

EXTERNAL_SIS_IMPORTER = settings.EXTERNAL_SIS_IMPORTER

_module = import_module(f'.{EXTERNAL_SIS_IMPORTER}.section_import', package=__name__)
SectionImporter = _module.SectionImporter
