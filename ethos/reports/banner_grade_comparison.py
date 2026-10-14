"""Banner vs MyCE Grades: a CSV of each registration's grade and status in both systems.

The comparison itself lives in ``ethos.grade_comparison``; this is the report
form (registered through ``REPORTS`` in apps.py) and its CSV writer. Runs as a
background report job: Banner is read class by class (about two calls each).
"""
import csv
import datetime
import io

from django import forms
from django.core.files.base import ContentFile
from django.urls import reverse_lazy

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.backends.storage_backend import PrivateMediaStorage
from cis.campus_gate import get_accessible_campuses, scope_report_by_campus
from cis.models.course import Campus
from cis.models.section import StudentRegistration
from cis.models.term import Term

from ..grade_comparison import COLUMNS, compare


def _values(data, key):
    """Report data is dict(request.POST): every value is a list of strings."""
    value = data.get(key) or []
    return [v for v in (value if isinstance(value, (list, tuple)) else [value]) if v]


def _flag(data, key):
    return bool(_values(data, key))


class banner_grade_comparison(forms.Form):
    """Grade and registration status in Banner vs MyCE, per registration."""

    campus = forms.ModelMultipleChoiceField(
        queryset=Campus.objects.none(), required=True, label='Campus')
    term = forms.ModelMultipleChoiceField(
        queryset=Term.objects.none(), label='Term(s)',
        help_text='Select one or more terms.')
    registration_status = forms.MultipleChoiceField(
        choices=StudentRegistration.STATUS_OPTIONS, required=False,
        label='MyCE Registration Status(es)',
        help_text='Leave blank to include every status.')
    only_differences = forms.BooleanField(
        required=False, label='Only rows that differ',
        help_text='Leave out registrations whose grade and status match.')
    include_banner_only = forms.BooleanField(
        required=False, initial=True, label='Include Banner-only registrations',
        help_text='Students registered in the Banner class with no MyCE registration.')

    roles = []
    request = None

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', 'Generate Report'))
        self.fields['term'].queryset = Term.objects.all().order_by('-code')
        if self.request:
            self.helper.form_action = reverse_lazy(
                'report:run_report', args=[request.GET.get('report_id')])
            self.fields['campus'].queryset = get_accessible_campuses(self.request.user)

    def get_result(self, data, user=None):
        """(selected registrations, every registration of the same terms and campus)."""
        everything = StudentRegistration.objects.filter(
            class_section__term__id__in=_values(data, 'term'))
        everything = scope_report_by_campus(
            everything, user, _values(data, 'campus'),
            campus_path='class_section__course__campus')
        selected = everything
        statuses = _values(data, 'registration_status')
        if statuses:
            selected = selected.filter(status__in=statuses)
        selected = selected.order_by(
            'class_section__term__code', 'class_section__course__name',
            'class_section__class_number', 'student__user__last_name',
            'student__user__first_name')
        return selected, everything

    def run(self, task, data):
        selected, everything = self.get_result(data, user=getattr(task, 'created_by', None))

        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        for row in compare(selected, everything,
                           include_banner_only=_flag(data, 'include_banner_only'),
                           only_differences=_flag(data, 'only_differences')):
            writer.writerow(row)

        file_name = ('banner_vs_myce_grades_'
                     f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        path = f"reports/{datetime.datetime.now().strftime('%Y/%m')}/{task.id}/{file_name}"
        storage = PrivateMediaStorage()
        path = storage.save(path, ContentFile(stream.getvalue().encode('utf-8')))
        return storage.url(path)
