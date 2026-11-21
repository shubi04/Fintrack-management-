from .models import Category


def shell(request):
    if request.user.is_authenticated:
        return {"all_categories": Category.objects.filter(user=request.user)}
    return {}
