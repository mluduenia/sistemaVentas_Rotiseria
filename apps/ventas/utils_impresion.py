import logging
import requests

logger = logging.getLogger(__name__)

FLASK_PRINT_URL = "http://127.0.0.1:8085/print"


def generar_comanda_cocina(venta, ancho=42):
    """
    Genera el texto plano para la comanda de cocina.
    """
    def center(texto):
        return str(texto).center(ancho)

    lineas = []
    lineas.append(center("*** COMANDA DE COCINA ***"))
    lineas.append("=" * ancho)

    numero_pedido = f"#{venta.id:04d}"
    lineas.append(f"PEDIDO: {numero_pedido}")
    lineas.append(f"HORA: {venta.fecha.strftime('%H:%M')}")

    nombre = venta.nombre_retiro.upper() if venta.nombre_retiro else "S/N"
    lineas.append(f"RETIRA: {nombre}")
    lineas.append("=" * ancho)

    lineas.append("CANT - PRODUCTO")
    lineas.append("-" * ancho)

    for det in venta.detalles.all():
        cant = f"{det.cantidad}x"
        prod = det.producto.nombre.upper()
        if len(prod) > 30:
            prod = prod[:30] + "..."
        lineas.append(f"{cant} {prod}")

    lineas.append("=" * ancho)
    lineas.append(center(f"*PEDIDO-{venta.id:04d}*"))
    lineas.append(center("Escanear aqui ->"))
    lineas.append("=" * ancho)
    lineas.append(center("*** FIN DE COMANDA ***"))
    lineas.append("\n\n\n\n")

    return "\n".join(lineas)


def _resolver_nombre_impresora_cocina():
    """
    Devuelve el nombre EXACTO de la impresora Windows para cocina.
    """
    from django.db import models as dj_models
    from apps.configuracion.models import Impresora, EmpresaConfig

    config = EmpresaConfig.objects.first()

    imp_fk = getattr(config, 'impresora_cocina', None)
    if imp_fk and getattr(imp_fk, 'activa', False):
        return imp_fk.clave_estacion, f'FK Impresora#{imp_fk.id}'

    for patron in ('cocina', 'comanda'):
        imp = Impresora.objects.filter(activa=True).filter(
            dj_models.Q(clave_estacion__icontains=patron) |
            dj_models.Q(nombre__icontains=patron)
        ).first()
        if imp:
            return imp.clave_estacion, f'Impresora#{imp.id} (match {patron!r})'

    if config and getattr(config, 'impresora_cocina_ip', None):
        return config.impresora_cocina_ip, 'EmpresaConfig.impresora_cocina_ip'

    return None, None


def enviar_comanda_cocina(venta):
    """
    Genera el texto de la comanda y lo manda al Flask local.
    """
    from apps.configuracion.models import EmpresaConfig

    config = EmpresaConfig.objects.first()
    if not config or not config.modulo_cocina:
        return {'success': False, 'error': 'modulo_cocina apagado'}

    nombre_impresora, origen = _resolver_nombre_impresora_cocina()

    if not nombre_impresora:
        logger.warning(f"Comanda cocina: no hay impresora de cocina configurada (venta #{venta.id}).")
        return {'success': False, 'error': 'Sin impresora de cocina configurada'}

    texto = generar_comanda_cocina(venta)

    payload = {
        'contenido': texto,
        'tipo': 'comanda',
        'cortar': True,
        'abrir_cajon': False,
        'modo': 'texto',
        'impresora': nombre_impresora,
    }

    try:
        resp = requests.post(FLASK_PRINT_URL, json=payload, timeout=5)
        if resp.ok:
            logger.info(f"Comanda cocina OK venta #{venta.id} → '{nombre_impresora}' (origen: {origen})")
            return resp.json()
        logger.error(f"Comanda cocina HTTP {resp.status_code}: {resp.text[:200]}")
        return {'success': False, 'error': f'HTTP {resp.status_code}', 'detalle': resp.text[:200]}
    except requests.exceptions.ConnectionError:
        logger.error("No se pudo conectar con el servicio de impresión (127.0.0.1:8085). ¿El Flask está corriendo?")
        return {'success': False, 'error': 'Flask no disponible'}
    except Exception as e:
        logger.exception(f"Error inesperado enviando comanda a Flask: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================
# 🔽 NUEVA LÓGICA: ENVIAR COMANDAS POR ESTACIÓN (CATEGORÍA)
# ============================================================

def enviar_comandas_por_estacion(venta):
    """
    Separa los productos según la estación configurada en su categoría.
    Si la categoría tiene estacion_impresion='', no imprime nada para esa categoría.
    """
    from apps.configuracion.models import EmpresaConfig
    
    config = EmpresaConfig.objects.first()
    if not config or not config.modulo_cocina:
        return

    # 1. Agrupamos los ítems por la estación de su categoría
    grupos = {}
    for det in venta.detalles.all():
        categoria = det.producto.categoria
        estacion = getattr(categoria, 'estacion_impresion', 'comanda') if categoria else 'comanda'
        
        if not estacion:
            continue 
            
        if estacion not in grupos:
            grupos[estacion] = []
        grupos[estacion].append(det)

    # 2. Mandamos un ticket a cada estación que tenga productos
    for estacion, detalles in grupos.items():
        # Armamos el texto
        texto = _generar_comanda_por_items(venta, detalles, estacion)
        
        payload = {
            'contenido': texto,
            'tipo': estacion,
            'modo': 'texto',
            'cortar': True,
        }
        
        try:
            requests.post(FLASK_PRINT_URL, json=payload, timeout=5)
            logger.info(f"Comanda enviada a estación '{estacion}' para venta #{venta.id}")
        except Exception as e:
            logger.error(f"Error enviando comanda a {estacion}: {e}")


def _generar_comanda_por_items(venta, detalles, estacion):
    """Arma el texto de la comanda solo con los productos de esa estación."""
    ancho = 42
    def center(texto): return str(texto).center(ancho)
    
    lineas = []
    if estacion == 'comanda':
        lineas.append(center("*** COMANDA DE COCINA ***"))
    elif estacion == 'bebidas':
        lineas.append(center("*** BARRA / BEBIDAS ***"))
    elif estacion == 'postres':
        lineas.append(center("*** POSTRES ***"))
    else:
        lineas.append(center(f"*** {estacion.upper()} ***"))
        
    lineas.append("=" * ancho)
    lineas.append(f"PEDIDO: #{venta.id:04d}")
    lineas.append(f"HORA: {venta.fecha.strftime('%H:%M')}")
    nombre = venta.nombre_retiro.upper() if venta.nombre_retiro else "S/N"
    lineas.append(f"RETIRA: {nombre}")
    lineas.append("=" * ancho)
    lineas.append("CANT - PRODUCTO")
    lineas.append("-" * ancho)

    for det in detalles:
        cant = f"{det.cantidad}x"
        prod = det.producto.nombre.upper()
        if len(prod) > 30:
            prod = prod[:30] + "..."
        lineas.append(f"{cant} {prod}")

    lineas.append("=" * ancho)
    lineas.append("\n\n\n\n")
    
    return "\n".join(lineas)