"""Operator-facing configuration for the change-notification poller.

Edited at ``/ce/settings/``. Saving this setting also upserts the ``CronTab``
row that schedules ``poll_ethos_messages`` — the cron expression IS a field
here, the same way ``cis.settings.registration_status_email`` schedules
``send_registrations_to_sis``.

Everything here ships **inert**: ``is_active`` defaults to ``No``, so installing
the release and letting the cron fire changes no behavior until someone
deliberately turns polling on.

Deployment-level configuration deliberately does NOT live here — the retention
windows, the per-resource auto-consume map, and the handler registry stay in
Django settings (fed from ``SECRETS``), because they are not things a CE admin
should be able to change from a web form. See ``consume/config.py``.

Note on ``key``: it is a stable literal rather than ``str(__name__)``. This
package runs under two different import roots — ``ethos.settings.ethos_consume``
when pip-installed and ``ethos.ethos.settings.ethos_consume`` as a submodule —
so deriving the key from ``__name__`` would silently point at a different
Setting row in each mode, orphaning the operator's configuration on the move
between them.
"""
from django import forms
from django.http import JsonResponse
from django.urls import reverse_lazy

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.models.settings import Setting
from cis.validators import validate_cron

POLL_COMMAND = 'poll_ethos_messages'

# Ethos caps a single /consume request at 1000 notifications, and separately
# caps the response at 1 MB — so a batch may come back short even at the max.
LIMIT_MIN = 1
LIMIT_MAX = 1000

BATCHES_MIN = 1
BATCHES_MAX = 100

DEFAULTS = {
    'is_active': 'No',
    'limit': 100,
    'max_batches': 1,
    'consume_after_poll': 'No',
    'cron': '0 * * * *',
}


class SettingForm(forms.Form):

    YES_NO = [
        ('', 'Select'),
        ('Yes', 'Yes'),
        ('No', 'No'),
    ]

    is_active = forms.ChoiceField(
        choices=YES_NO,
        label='Enable Polling',
        help_text='When No, the scheduled job exits immediately without calling Ethos. '
                  'This is the master switch — the cron row can stay in place while polling is off.',
        widget=forms.Select(attrs={'class': 'col-md-4 col-sm-12'}))

    limit = forms.IntegerField(
        min_value=LIMIT_MIN,
        max_value=LIMIT_MAX,
        label='Notifications per Request',
        help_text=f'How many change-notifications to request per call to /consume '
                  f'({LIMIT_MIN}-{LIMIT_MAX}). Ethos also caps the response at 1 MB, '
                  f'so fewer may come back than requested even when more are queued.',
        widget=forms.NumberInput(attrs={'class': 'col-md-4 col-sm-12'}))

    max_batches = forms.IntegerField(
        min_value=BATCHES_MIN,
        max_value=BATCHES_MAX,
        label='Batches per Run',
        help_text=f'How many requests one scheduled run may make ({BATCHES_MIN}-{BATCHES_MAX}). '
                  f'Notifications per Request x Batches per Run is the most a single run can read, '
                  f'so raise this if the queue grows faster than the schedule drains it.',
        widget=forms.NumberInput(attrs={'class': 'col-md-4 col-sm-12'}))

    consume_after_poll = forms.ChoiceField(
        choices=YES_NO,
        label='Consume After Polling',
        help_text='When Yes, the scheduled run also dispatches newly stored notifications to '
                  'their handlers after storing them. Each resource type must ALSO be enabled '
                  'in the deployment-level auto-consume map, so this alone does not start '
                  'changing records.',
        widget=forms.Select(attrs={'class': 'col-md-4 col-sm-12'}))

    cron = forms.CharField(
        max_length=50,
        help_text='Min Hr Day Month WeekDay',
        label='Cron Expression for Polling Ethos',
        validators=[validate_cron])

    def _to_python(self):
        """Return the cleaned form as a dict, and sync the CronTab row.

        The cron row is upserted rather than created, so editing the schedule
        moves the existing job instead of accumulating duplicates.
        """
        from cis.models.crontab import CronTab

        cron, _created = CronTab.objects.get_or_create(command=POLL_COMMAND)
        cron.cron = self.cleaned_data.get('cron')
        cron.save()

        return {key: value for key, value in self.cleaned_data.items()}


class ethos_consume(SettingForm):
    key = 'ethos.settings.ethos_consume'

    title = 'Ethos Change Notifications'
    category = [
        1,
    ]

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.request = request
        self.helper = FormHelper()
        self.helper.attrs = {'target': '_blank'}
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse_lazy(
            'setting:run_record', args=[request.GET.get('report_id')])
        self.helper.add_input(Submit('submit', 'Save Setting'))

    def install(self):
        from cis.models.crontab import CronTab

        try:
            setting = Setting.objects.get(key=self.key)
        except Setting.DoesNotExist:
            setting = Setting()
            setting.key = self.key

        setting.value = dict(DEFAULTS)
        setting.save()

        # Create the schedule up front so the operator only has to flip
        # is_active, rather than also discovering that the cron row does not
        # exist until the form is saved once. Safe because the command exits
        # immediately while is_active is No.
        cron, created = CronTab.objects.get_or_create(
            command=POLL_COMMAND, defaults={'cron': DEFAULTS['cron']})
        if not created and not cron.cron:
            cron.cron = DEFAULTS['cron']
            cron.save()

    def run_record(self):
        try:
            setting = Setting.objects.get(key=self.key)
        except Setting.DoesNotExist:
            setting = Setting()
            setting.key = self.key

        setting.value = self._to_python()
        setting.save()

        return JsonResponse({
            'message': 'Successfully saved settings',
            'status': 'success'})

    # --- read helpers -------------------------------------------------
    # Each returns None when unset, so callers can fall back to the
    # Django-settings default rather than treating "unconfigured" as a value.

    @classmethod
    def from_db(cls):
        try:
            return Setting.objects.get(key=cls.key).value or {}
        except Setting.DoesNotExist:
            return {}

    @classmethod
    def is_poll_enabled(cls):
        return str(cls.from_db().get('is_active', DEFAULTS['is_active'])).lower() == 'yes'

    @classmethod
    def consume_after_poll_enabled(cls):
        return str(
            cls.from_db().get('consume_after_poll', DEFAULTS['consume_after_poll'])
        ).lower() == 'yes'

    @classmethod
    def _int(cls, field, low, high):
        raw = cls.from_db().get(field)
        if raw in (None, ''):
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return value if low <= value <= high else None

    @classmethod
    def get_limit(cls):
        return cls._int('limit', LIMIT_MIN, LIMIT_MAX)

    @classmethod
    def get_max_batches(cls):
        return cls._int('max_batches', BATCHES_MIN, BATCHES_MAX)
