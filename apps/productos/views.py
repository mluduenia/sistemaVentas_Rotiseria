from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.db.models import Sum
import logging
from datetime import date, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from .models import Producto, Categoria, Proveedor, MovimientoStock, Lote, StockLote

logger = logging.getLogger(__name__)

from .models import Producto, Categoria, Proveedor, MovimientoStock
from .forms import ProductoForm, CategoriaForm, ProveedorForm


# ==========================================
# --- FUNCIONES AUXILIARES DE PERMISOS ---
# ==========================================

def es_admin_o_super(user):
    """Permite el acceso a Superusuarios o miembros del grupo 'Administrador'."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name='Administrador').exists()
    )

def es_cajero_o_superior(user):
    """Permite el acceso a Cajeros, Administradores o Superusuarios."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=['Administrador', 'Cajero']).exists()
    )


# ==========================================
# --- PRODUCTOS ---
# ==========================================

# Permite ver la lista a cualquier usuario logueado (Cajero, Admin, Superuser)
@login_required
def lista_productos(request):
    """Listado y consulta de productos con filtros."""
    from .models import StockSucursal
    from apps.configuracion.models import Sucursal

    productos = Producto.objects.select_related('categoria', 'proveedor').all().order_by('nombre')

    q = request.GET.get('q', '').strip()
    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(codigo_barra__icontains=q)
        )

    cat_id = request.GET.get('categoria')
    if cat_id:
        productos = productos.filter(categoria_id=cat_id)

    prov_id = request.GET.get('proveedor')
    if prov_id:
        productos = productos.filter(proveedor_id=prov_id)

    categorias = Categoria.objects.all()
    proveedores = Proveedor.objects.all()

    # Bandera para saber si el usuario puede modificar
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()

    # Armar desglose de stock por producto
    sucursales = list(Sucursal.objects.filter(activa=True).order_by('-es_central', 'nombre'))
    productos_con_stock = []

    for p in productos:
        stocks = {}
        for ss in StockSucursal.objects.filter(producto=p).select_related('sucursal'):
            stocks[ss.sucursal_id] = ss.cantidad

        productos_con_stock.append({
            'producto': p,
            'stocks': [
                {
                    'sucursal': s,
                    'cantidad': stocks.get(s.id, 0),
                }
                for s in sucursales
            ],
        })

    context = {
        'productos_con_stock': productos_con_stock,
        'sucursales': sucursales,
        'categorias': categorias,
        'proveedores': proveedores,
        'q': q,
        'es_admin': es_admin,
    }
    return render(request, 'productos/lista_productos.html', context)


@login_required
@user_passes_test(es_admin_o_super)
def crear_producto(request):
    """Creación de un producto (Exclusivo Administradores y Superusuarios)."""
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Producto registrado correctamente!')
            return redirect('productos:lista_productos')
        else:
            messages.error(request, 'No se pudo guardar el producto. Revisa los errores marcados.')
    else:
        form = ProductoForm()

    return render(request, 'productos/form_producto.html', {
        'form': form,
        'titulo': 'Nuevo Producto'
    })


@login_required
@user_passes_test(es_admin_o_super)
def editar_producto(request, pk):
    """Edición de producto (Exclusivo Administradores y Superusuarios)."""
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Producto actualizado correctamente!')
            return redirect('productos:lista_productos')
        else:
            messages.error(request, 'No se pudieron guardar los cambios. Revisa los errores.')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'productos/form_producto.html', {
        'form': form,
        'producto': producto,
        'titulo': 'Editar Producto'
    })


@login_required
@user_passes_test(es_admin_o_super)
def eliminar_producto(request, pk):
    """
    Dar de baja un producto (soft delete).
    NO lo elimina: lo marca como inactivo para conservar historial.
    """
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == 'POST':
        if not producto.activo:
            messages.warning(request, f'El producto "{producto.nombre}" ya estaba dado de baja.')
            return redirect('productos:lista_productos')

        nombre = producto.nombre
        producto.activo = False
        producto.save()

        # Registrar en auditoría (opcional)
        try:
            from apps.configuracion.audit import registrar_log
            registrar_log(
                request,
                accion='BAJA',
                descripcion=f'Producto dado de baja: {nombre} (ID: {producto.id})',
                modelo='Producto',
                objeto_id=producto.id,
                nivel='WARNING',
            )
        except Exception:
            pass

        messages.success(request, f'Producto "{nombre}" dado de baja correctamente.')

    return redirect('productos:lista_productos')


# ==========================================
# --- CATEGORÍAS / RUBROS ---
# ==========================================

@login_required
@user_passes_test(es_cajero_o_superior)
def lista_categorias(request):
    """Listado de categorías/rubros."""
    categorias = Categoria.objects.all().order_by('nombre')
    return render(request, 'productos/lista_categorias.html', {'categorias': categorias})


@login_required
@user_passes_test(es_admin_o_super)
def crear_categoria(request):
    """Creación de categoría (Exclusivo Administradores y Superusuarios)."""
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría registrada con éxito.')
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'productos:lista_categorias')
        else:
            messages.error(request, 'Error al guardar la categoría.')
    else:
        form = CategoriaForm()
    return render(request, 'productos/form_categoria.html', {'form': form})


@login_required
@user_passes_test(es_admin_o_super)
def editar_categoria(request, pk):
    """Edición de categoría (Exclusivo Administradores y Superusuarios)."""
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('productos:lista_categorias')
        else:
            messages.error(request, 'Error al actualizar la categoría.')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'productos/form_categoria.html', {'form': form, 'categoria': categoria})


@login_required
@user_passes_test(es_admin_o_super)
def eliminar_categoria(request, pk):
    """Eliminación de categoría (Exclusivo Administradores y Superusuarios)."""
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        nombre = categoria.nombre
        categoria.delete()
        messages.success(request, f'Categoría "{nombre}" eliminada.')
    return redirect('productos:lista_categorias')


# ==========================================
# --- PROVEEDORES ---
# ==========================================

@login_required
@user_passes_test(es_cajero_o_superior)
def lista_proveedores(request):
    """Listado de proveedores."""
    proveedores = Proveedor.objects.all().order_by('nombre_o_razon_social')
    return render(request, 'productos/lista_proveedores.html', {'proveedores': proveedores})


@login_required
@user_passes_test(es_admin_o_super)
def crear_proveedor(request):
    """Creación de proveedor (Exclusivo Administradores y Superusuarios)."""
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor registrado con éxito.')
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'productos:lista_proveedores')
        else:
            messages.error(request, 'Error al guardar el proveedor.')
    else:
        form = ProveedorForm()
    return render(request, 'productos/form_proveedor.html', {'form': form})


@login_required
@user_passes_test(es_admin_o_super)
def editar_proveedor(request, pk):
    """Edición de proveedor (Exclusivo Administradores y Superusuarios)."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado correctamente.')
            return redirect('productos:lista_proveedores')
        else:
            messages.error(request, 'Error al actualizar el proveedor.')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'productos/form_proveedor.html', {'form': form, 'proveedor': proveedor})


@login_required
@user_passes_test(es_admin_o_super)
def eliminar_proveedor(request, pk):
    """Eliminación de proveedor (Exclusivo Administradores y Superusuarios)."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        nombre = proveedor.nombre_o_razon_social
        proveedor.delete()
        messages.success(request, f'Proveedor "{nombre}" eliminado.')
    return redirect('productos:lista_proveedores')


# ==========================================
# --- HISTORIAL DE MOVIMIENTOS DE STOCK ---
# ==========================================

@login_required
def movimientos_stock_view(request):
    """Historial y auditoría de entradas y salidas de stock (Accesible por Cajeros y Administradores)."""
    movimientos = MovimientoStock.objects.all().select_related('producto').order_by('-fecha')

    query = request.GET.get('q', '').strip()
    tipo_mov = request.GET.get('tipo', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')

    if query:
        movimientos = movimientos.filter(
            Q(producto__nombre__icontains=query) |
            Q(producto__codigo_barra__icontains=query) |
            Q(motivo__icontains=query)
        )

    if tipo_mov:
        movimientos = movimientos.filter(tipo=tipo_mov)

    if fecha_desde:
        movimientos = movimientos.filter(fecha__date__gte=fecha_desde)

    if fecha_hasta:
        movimientos = movimientos.filter(fecha__date__lte=fecha_hasta)

    paginator = Paginator(movimientos, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Identificar si es Administrador o Superusuario
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()

    context = {
        'page_obj': page_obj,
        'query': query,
        'tipo_mov': tipo_mov,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'es_admin': es_admin,
    }
    return render(request, 'productos/movimientos_stock.html', context)

# ==========================================
# --- STOCK POR SUCURSAL ---
# ==========================================

@login_required
@user_passes_test(es_admin_o_super)
def cargar_stock_sucursal_view(request, producto_id):
    """
    Carga stock de un producto en una sucursal específica.
    Actualiza StockSucursal y recalcula Producto.stock_actual.
    """
    from apps.configuracion.models import Sucursal
    from .models import StockSucursal

    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        sucursal_id = request.POST.get('sucursal', '').strip()
        cantidad = request.POST.get('cantidad', '0').strip()
        motivo = request.POST.get('motivo', 'Carga inicial').strip()
        
        # 🔽 NUEVOS CAMPOS DE LOTE
        codigo_lote = request.POST.get('codigo_lote', '').strip()
        fecha_vencimiento = request.POST.get('fecha_vencimiento', '').strip()

        # Validaciones
        errores = []
        if not sucursal_id:
            errores.append('Tenés que elegir una sucursal.')
        try:
            cantidad = int(cantidad)
            if cantidad == 0:
                errores.append('La cantidad no puede ser cero.')
        except ValueError:
            errores.append('La cantidad debe ser un número entero.')
            
        # 🔽 VALIDACIÓN DE LOTES
        if producto.maneja_lotes and not codigo_lote:
            errores.append('Este producto requiere un código de lote.')
        if producto.maneja_vencimiento and not fecha_vencimiento:
            errores.append('Este producto requiere una fecha de vencimiento.')

        if errores:
            for err in errores:
                messages.error(request, err)
            return redirect('productos:cargar_stock_sucursal', producto_id=producto.id)

        sucursal = get_object_or_404(Sucursal, id=sucursal_id)

        try:
            with transaction.atomic():
                # 1. Si el producto maneja lotes, creamos el lote
                lote_obj = None
                if producto.maneja_lotes:
                    # Convertimos la fecha string a date de Python
                    from datetime import datetime
                    f_venc = datetime.strptime(fecha_vencimiento, '%Y-%m-%d').date() if fecha_vencimiento else None
                    
                    lote_obj = Lote.objects.create(
                        producto=producto,
                        codigo_lote=codigo_lote,
                        fecha_vencimiento=f_venc,
                        costo_unitario=producto.precio_costo
                    )
                    
                    # Actualizamos el StockLote
                    sl = StockLote.objects.create(
                        lote=lote_obj,
                        sucursal=sucursal,
                        cantidad_disponible=cantidad
                    )

                # 2. Actualizar el StockSucursal (el de siempre)
                ss, created = StockSucursal.objects.get_or_create(
                    producto=producto,
                    sucursal=sucursal,
                    defaults={'cantidad': 0}
                )
                ss.cantidad += cantidad
                if ss.cantidad < 0:
                    messages.error(request, f'No podés restar más de lo que hay. Stock actual: {ss.cantidad - cantidad}')
                    return redirect('productos:cargar_stock_sucursal', producto_id=producto.id)
                ss.save()

                # 3. Recalcular el stock total del producto
                total = StockSucursal.objects.filter(producto=producto).aggregate(
                    t=Sum('cantidad')
                )['t'] or 0
                producto.stock_actual = total
                producto.save()

                # 4. Registrar el movimiento (ahora con el lote asociado)
                MovimientoStock.objects.create(
                    producto=producto,
                    sucursal=sucursal,
                    tipo='AJUSTE' if cantidad < 0 else 'ENTRADA',
                    cantidad=abs(cantidad),
                    motivo=f'{motivo} - {sucursal.nombre}',
                    lote=lote_obj  # 🔽 Vinculamos el lote
                )

            messages.success(
                request,
                f'Stock actualizado: {cantidad:+d} en {sucursal.nombre}. '
                f'Total del producto: {total}'
            )
            return redirect('productos:lista_productos')

        except Exception as e:
            logger.exception(f"Error cargando stock: {e}")
            messages.error(request, f'Error al cargar stock: {str(e)}')

    # GET: mostrar el formulario
    sucursales = Sucursal.objects.filter(activa=True).order_by('-es_central', 'nombre')

    # Stock actual del producto por sucursal
    stock_actual = {}
    for ss in StockSucursal.objects.filter(producto=producto).select_related('sucursal'):
        stock_actual[ss.sucursal_id] = ss.cantidad

    context = {
        'producto': producto,
        'sucursales': sucursales,
        'stock_actual': stock_actual,
    }
    return render(request, 'productos/cargar_stock_sucursal.html', context)

@login_required
@user_passes_test(es_admin_o_super)
def reactivar_producto(request, pk):
    """Reactiva un producto dado de baja."""
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == 'POST':
        if producto.activo:
            messages.warning(request, f'El producto "{producto.nombre}" ya estaba activo.')
            return redirect('productos:lista_productos')

        producto.activo = True
        producto.save()

        try:
            from apps.configuracion.audit import registrar_log
            registrar_log(
                request,
                accion='REACTIVAR',
                descripcion=f'Producto reactivado: {producto.nombre} (ID: {producto.id})',
                modelo='Producto',
                objeto_id=producto.id,
            )
        except Exception:
            pass

        messages.success(request, f'Producto "{producto.nombre}" reactivado correctamente.')

    return redirect('productos:lista_productos')

@login_required
@user_passes_test(es_admin_o_super)
def api_lotes_producto(request, producto_id):
    """Devuelve los lotes con stock disponible de un producto en formato JSON."""
    # Buscamos los lotes que tengan stock mayor a 0
    stocks = StockLote.objects.filter(
        lote__producto_id=producto_id,
        cantidad_disponible__gt=0
    ).select_related('lote')
    
    # Agrupamos por lote (por si hay stock en varias sucursales)
    lotes_dict = {}
    for s in stocks:
        if s.lote.id not in lotes_dict:
            lotes_dict[s.lote.id] = {
                'codigo': s.lote.codigo_lote,
                'vencimiento': s.lote.fecha_vencimiento.strftime('%d/%m/%Y') if s.lote.fecha_vencimiento else None,
                'cantidad': 0
            }
        lotes_dict[s.lote.id]['cantidad'] += s.cantidad_disponible

    # Convertimos a lista y ordenamos por fecha de vencimiento (los más próximos primero)
    lotes = list(lotes_dict.values())
    lotes.sort(key=lambda x: x['vencimiento'] if x['vencimiento'] else '9999')

    return JsonResponse({'lotes': lotes})

@login_required
@user_passes_test(es_admin_o_super)
def alertas_vencimiento_view(request):
    """
    Muestra los lotes que están por vencer o ya vencidos.
    Por defecto, muestra los que vencen en los próximos 30 días.
    """
    dias_alerta = int(request.GET.get('dias', 30))
    hoy = date.today()
    fecha_limite = hoy + timedelta(days=dias_alerta)

    # Buscamos lotes con stock > 0 que venzan antes de la fecha límite (incluye vencidos)
    lotes_alerta = StockLote.objects.filter(
        cantidad_disponible__gt=0,
        lote__fecha_vencimiento__isnull=False,
        lote__fecha_vencimiento__lte=fecha_limite
    ).select_related('lote', 'lote__producto', 'sucursal').order_by('lote__fecha_vencimiento')

    # Separamos los ya vencidos de los que están por vencer
    vencidos = []
    por_vencer = []

    for sl in lotes_alerta:
        # Calculamos los días restantes
        dias_restantes = (sl.lote.fecha_vencimiento - hoy).days
        
        sl.dias_restantes = dias_restantes # Lo inyectamos en el objeto para usarlo en el template

        if dias_restantes < 0:
            vencidos.append(sl)
        else:
            por_vencer.append(sl)

    context = {
        'vencidos': vencidos,
        'por_vencer': por_vencer,
        'dias_alerta': dias_alerta,
        'total_items': len(vencidos) + len(por_vencer),
    }
    return render(request, 'productos/alertas_vencimiento.html', context)