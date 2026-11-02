from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages

class DemoReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 🔽 1. EXCLUIR EL LOGIN Y LOGOUT (para que no te saque al intentar entrar)
        if request.path in ['/usuarios/login/', '/usuarios/logout/'] or '/admin/' in request.path:
            return self.get_response(request)

        # 🔽 2. SI ESTÁ EN MODO DEMO Y ES UN POST (Guardar/Modificar)
        if request.user.is_authenticated and request.session.get('es_demo'):
            if request.method == 'POST':
                # Si es una petición AJAX (como el POS), devolvemos un JSON falso
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({
                        'status': 'success', 
                        'message': 'Acción simulada en Demo (no se guardó nada).'
                    })
                
                # Si es un formulario normal (ej. crear producto), lo rebotamos
                messages.warning(request, 'Estás en Modo Demo. No podés realizar modificaciones reales.')
                
                # Lo devolvemos a la misma página o al dashboard
                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return redirect(referer)
                return redirect('core:dashboard')
                
        return self.get_response(request)