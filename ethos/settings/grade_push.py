"""Banner Grade Push: the SIS GUIDS keys the final-grade push sends to Banner.

The values live in the cis "SIS GUIDS" setting (``guids`` JSON blob), not in a
row of their own: ``key`` is the SIS GUIDS key so the settings pages apply its
edit permission and the superuser JSON view shows the blob being edited.
``install()`` therefore writes nothing. Saving goes through
``grade_push_config.apply`` (also used by ``set_grade_push_guids``).

A sample section registration drives the Look up button (see
``staticfiles/ethos/js/grade_push_settings.js``) and, when given on save, a
check that every mapped grade is one of that registration's grade options.
"""
import json
import re

from django import forms
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html, format_html_join

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Layout, Submit

from cis.settings.sis_settings import sis_settings

from ..grade_push import unmapped_grades
from ..grade_push_config import (
    PRIMARY_INSTRUCTOR, GradePushConfigError, apply, load, normalise_guid)
from ..grade_push_lookup import BannerLookupError, grade_options
from ..views._client import ethos_client_or_error


_LETTER_RE = re.compile(r'^[A-Za-z0-9+\-/.*]{1,10}$')
PERSON = 'person'
SUBMITTED_BY_CHOICES = (
    (PRIMARY_INSTRUCTOR, "Section's primary instructor"),
    (PERSON, 'This Banner person'),
)


def _guid_field(label, help_text, required=True):
    return forms.CharField(label=label, help_text=help_text, required=required, max_length=36)


class grade_push(forms.Form):
    key = sis_settings.key
    title = 'Banner Grade Push'
    category = [1]

    sample_registration = _guid_field(
        'Sample Section Registration',
        'Any Banner section-registration GUID that uses the grade scheme of your classes. '
        'Look up fills the fields below from it; on save, the grade map is checked against it. '
        'Not saved.', required=False)
    final_grade_type = _guid_field(
        'Final Grade Type', 'Banner section grade type sent with every grade (FINAL).')
    grade_map = forms.CharField(
        label='Grade Map', widget=forms.Textarea(attrs={'rows': 6}),
        help_text='JSON object of MyCE grade → Banner grade GUID. Look up shows one dropdown per grade.')
    submitted_by_source = forms.ChoiceField(
        label='Submitted By', choices=SUBMITTED_BY_CHOICES, initial=PRIMARY_INSTRUCTOR,
        widget=forms.RadioSelect,
        help_text='Banner rejects grades without submittedBy. The primary instructor is '
                  "looked up in Banner for each grade's section when it is sent.")
    grade_submitted_by = _guid_field(
        'Banner Person GUID', 'Sent as submittedBy when "This Banner person" is chosen.',
        required=False)

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        if not self.initial.get('submitted_by_source'):
            # A copy: the settings overview passes its own values dict as initial.
            self.initial = dict(self.initial, submitted_by_source=PRIMARY_INSTRUCTOR)
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse_lazy(
            'setting:run_record', args=[request.GET.get('report_id')])
        self.helper.add_input(Submit('submit', 'Save Setting'))
        self.helper.layout = Layout(
            HTML(format_html(
                '<div id="grade-push-settings" data-lookup-url="{}"></div>'
                '<script src="/static/ethos/js/grade_push_settings.js"></script>',
                reverse('ethos:grade_push_lookup'))),
            *self.fields.keys())

    # --- validation ---------------------------------------------------------
    def _guid(self, name, required=True):
        raw = (self.cleaned_data.get(name) or '').strip()
        if not raw:
            if required:
                raise forms.ValidationError('This field is required.')
            return ''
        try:
            return normalise_guid(raw)
        except ValueError:
            raise forms.ValidationError(f'{raw!r} is not a GUID.')

    def clean_sample_registration(self):
        return self._guid('sample_registration', required=False)

    def clean_final_grade_type(self):
        return self._guid('final_grade_type')

    def clean_grade_submitted_by(self):
        required = self.data.get('submitted_by_source') == PERSON
        return self._guid('grade_submitted_by', required=required)

    def clean_grade_map(self):
        try:
            data = json.loads(self.cleaned_data.get('grade_map') or '')
        except ValueError:
            raise forms.ValidationError('Grade Map is not valid JSON.')
        if not isinstance(data, dict) or not data:
            raise forms.ValidationError('Grade Map must map at least one grade to a Banner GUID.')
        out = {}
        for letter, guid in data.items():
            letter = str(letter).strip()
            if not letter:
                raise forms.ValidationError('Grade Map has a blank grade.')
            if not _LETTER_RE.match(letter):
                raise forms.ValidationError(
                    f'Grade {letter!r}: use letters, digits and + - / . * only (max 10).')
            try:
                out[letter] = normalise_guid(guid)
            except ValueError:
                raise forms.ValidationError(f'Grade {letter}: {guid!r} is not a GUID.')
        return out

    def clean(self):
        cleaned = super().clean()
        registration = cleaned.get('sample_registration')
        grade_map = cleaned.get('grade_map')
        if not registration or not grade_map:
            return cleaned
        client, error = ethos_client_or_error(self.request)
        if client is None:
            self.add_error('sample_registration', error)
            return cleaned
        try:
            options = grade_options(client, registration)
        except BannerLookupError as exc:
            message = (f'Could not check against Banner (HTTP {exc.status}).' if exc.status
                       else f'Could not check against Banner: {exc}')
            self.add_error('sample_registration', message)
            return cleaned
        allowed = {g['id'] for g in options['grades']}
        bad = [letter for letter, guid in grade_map.items() if guid not in allowed]
        if bad:
            self.add_error('grade_map', 'Not a grade option of the sample registration: '
                           + ', '.join(bad))
        return cleaned

    # --- persistence ----------------------------------------------------------
    @classmethod
    def from_db(cls):
        try:
            current = load()
        except GradePushConfigError:
            current = {'final_grade_type': '', 'grade_map': {}, 'grade_submitted_by': '',
                       'submitted_by_primary_instructor': False}
        # '' when nothing is saved, so the overview says "Not set"; the form
        # itself then starts on the primary instructor (see __init__).
        if current['submitted_by_primary_instructor']:
            source = PRIMARY_INSTRUCTOR
        elif current['grade_submitted_by']:
            source = PERSON
        else:
            source = ''
        return {
            'sample_registration': '',
            'final_grade_type': current['final_grade_type'],
            'grade_map': json.dumps(current['grade_map'], indent=2) if current['grade_map'] else '',
            'submitted_by_source': source,
            'grade_submitted_by': current['grade_submitted_by'],
        }

    def run_record(self):
        try:
            person = self.cleaned_data['submitted_by_source'] == PERSON
            apply(final_grade_type=self.cleaned_data['final_grade_type'],
                  grade_map=self.cleaned_data['grade_map'], replace_grade_map=True,
                  submitted_by=self.cleaned_data['grade_submitted_by'] if person else None,
                  submitted_by_primary_instructor=not person)
        except GradePushConfigError as exc:
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
        return JsonResponse({'message': 'Successfully saved settings', 'status': 'success'})

    def install(self):
        """Nothing to seed: the values live in SIS GUIDS."""

    # --- settings overview ------------------------------------------------------
    @classmethod
    def overview_render(cls, values):
        """Display overrides for the settings overview (no Banner calls)."""
        try:
            grade_map = json.loads(values.get('grade_map') or '{}')
        except ValueError:
            grade_map = {}
        grade_map = grade_map if isinstance(grade_map, dict) else {}
        missing = unmapped_grades({'grade_map': grade_map})
        rows = format_html_join('', '<tr><td>{}</td><td><code>{}</code></td></tr>',
                                sorted(grade_map.items()))
        table = format_html(
            '<table class="table table-sm table-borderless mb-0"><tbody>{}</tbody></table>', rows) \
            if grade_map else format_html('<span class="text-danger">Not set</span>')
        if missing:
            table = format_html('{}<div class="text-danger small">No mapping for: {}</div>',
                                table, ', '.join(missing))
        if values.get('submitted_by_source') == PRIMARY_INSTRUCTOR:
            submitted_by = "Section's primary instructor"
        else:
            submitted_by = values.get('grade_submitted_by') \
                or 'Not set — Banner rejects grades without it'
        return {
            'final_grade_type': values.get('final_grade_type') or 'Not set',
            'grade_map': table,
            # The overview lists submitted_by_source; it shows the whole answer.
            'submitted_by_source': submitted_by,
            'grade_submitted_by': submitted_by,
        }
