import json

from django import template

register = template.Library()


@register.filter
def pretty_json(value):
    """Render a value as indented JSON. Accepts a dict/list or a JSON string."""
    if value is None:
        return ''
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return value  # not JSON — return as-is
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
