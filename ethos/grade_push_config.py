"""Read and write the grade-push keys inside the SIS GUIDS setting.

The grade push (``grade_push.push_final_grade``) reads three keys from the
``guids`` JSON blob of the cis "SIS GUIDS" setting:

    final_grade_type    {"id": guid}
    grade_map           {"<MyCE grade>": guid}
    grade_submitted_by  {"id": guid}

Shared by ``set_grade_push_guids`` and the "Banner Grade Push" setting, so both
edit only these keys, keep the rest of the blob and of the Setting row, and
save through the Setting model (the save lands in the setting's history).
SIS GUIDS is one row per campus on a multi-campus deployment: this works on
the row of the campus being served.
"""
import json
import uuid

from cis.campus_context import current_campus, is_multi_campus
from cis.models.settings import Setting, is_campus_scoped
from cis.settings.sis_settings import sis_settings

KEYS = ('final_grade_type', 'grade_map', 'grade_submitted_by')


class GradePushConfigError(Exception):
    """The stored SIS GUIDS blob cannot be edited safely."""


def normalise_guid(value):
    """`value` as a canonical lower-case GUID string; ValueError when it is not one."""
    return str(uuid.UUID(str(value).strip()))


def _parse_blob(raw):
    if not raw:
        return {}
    try:
        blob = json.loads(raw)
    except ValueError as exc:
        raise GradePushConfigError(
            f'SIS GUIDS is not valid JSON ({exc}); fix it on the settings page '
            'first. Nothing was changed.')
    if not isinstance(blob, dict):
        raise GradePushConfigError('SIS GUIDS is not a JSON object; nothing was changed.')
    return blob


def _row():
    return Setting.objects.filter(key=sis_settings.key).first()


def load():
    """The three keys, flattened: GUID strings ('' when unset) and the grade map."""
    setting = _row()
    blob = _parse_blob((setting.value or {}).get('guids') if setting else None)
    grade_map = blob.get('grade_map')
    return {
        'final_grade_type': (blob.get('final_grade_type') or {}).get('id') or '',
        'grade_map': dict(grade_map) if isinstance(grade_map, dict) else {},
        'grade_submitted_by': (blob.get('grade_submitted_by') or {}).get('id') or '',
    }


def apply(*, final_grade_type=None, grade_map=None, replace_grade_map=False,
          submitted_by=None, clear_submitted_by=False, dry_run=False):
    """Merge the given values into SIS GUIDS; returns (before, after) blobs."""
    setting = _row()
    value = dict(setting.value) if setting else {}
    before = _parse_blob(value.get('guids'))

    after = dict(before)
    if final_grade_type:
        after['final_grade_type'] = {'id': final_grade_type}
    if submitted_by:
        after['grade_submitted_by'] = {'id': submitted_by}
    if grade_map or replace_grade_map:
        base = {} if replace_grade_map else dict(before.get('grade_map') or {})
        base.update(grade_map or {})
        after['grade_map'] = base
    if clear_submitted_by:
        after.pop('grade_submitted_by', None)

    if dry_run:
        return before, after

    value['guids'] = json.dumps(after, indent=2)
    if setting is None:
        setting = Setting(key=sis_settings.key)
        if is_multi_campus() and is_campus_scoped(sis_settings.key):
            setting.campus = current_campus()
    setting.value = value
    setting.save()
    return before, after
