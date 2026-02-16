from django import template

register = template.Library()


@register.filter
def to_int(value):
    """Convert value to integer."""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0

