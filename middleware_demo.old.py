from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import logout
from django.core.cache import cache


class DemoTimeLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.get('es_demo'):
            inicio = request.session.get('demo_inicio', 0)
            ahora = timezone.now().timestamp()

            if ahora - inicio > 300:
                logout(request)
                cache.set('demo_bloqueada_hasta', ahora + 900, 900)
                return redirect('usuarios:login')

        return self.get_response(request)


class DemoReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ['/usuarios/login/', '/usuarios/logout/'] or '/admin/' in request.path:
            return self.get_response(request)

        if request.user.is_authenticated and request.session.get('es_demo'):
            if request.method == 'POST':
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'status': 'success', 'message': 'Acción simulada en Demo (no se guardó nada).'})

                messages.warning(request, 'Estás en Modo Demo. No podés realizar modificaciones reales.')
                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return redirect(referer)
                return redirect('core:dashboard')

        return self.get_response(request)