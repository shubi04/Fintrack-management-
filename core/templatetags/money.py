from decimal import Decimal
from django import template
from django.utils.html import format_html

register = template.Library()


def format_inr(value, decimals=2):
    v = Decimal(value or 0)
    neg, v = v < 0, abs(v)
    whole, _, frac = f"{v:.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail, groups = whole[:-3], whole[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if neg else ''}₹{whole}" + (f".{frac}" if decimals else "")


@register.filter
def inr(value, decimals=2):
    return format_html('<span class="amt">{}</span>', format_inr(value, int(decimals)))


@register.filter
def inr0(value):
    return inr(value, 0)


@register.filter
def abs_val(value):
    return abs(value)
