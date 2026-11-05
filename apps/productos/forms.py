from django import forms
from .models import Producto, Categoria, Proveedor

from apps.configuracion.models import Impresora

class CategoriaForm(forms.ModelForm):
    # 🔽 Creamos un campo dinámico que busca las impresoras activas
    estacion_impresion = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Impresora de Comanda"
    )

    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion', 'estacion_impresion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Bebidas, Almacén, Limpieza'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción opcional'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Armamos las opciones
        opciones = [('', 'No imprimir comanda')]
        
        # Buscamos las impresoras en la base de datos
        impresoras = Impresora.objects.filter(activa=True)
        for imp in impresoras:
            # Usamos la clave de estación como valor, y el nombre como etiqueta visible
            opciones.append((imp.clave_estacion, f"{imp.nombre} ({imp.clave_estacion})"))
            
        self.fields['estacion_impresion'].choices = opciones
        
class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre_o_razon_social', 'cuit', 'telefono', 'email', 'direccion']
        widgets = {
            'nombre_o_razon_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razón Social o Nombre'}),
            'cuit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '20-12345678-9'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono de contacto'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@proveedor.com'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección comercial'}),
        }

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'codigo_barra', 
            'nombre', 
            'categoria', 
            'proveedor',
            'precio_costo', 
            'precio_venta', 
            'alicuota_iva', 
            'stock_actual', 
            'stock_minimo', 
            'activo',
            'maneja_lotes',
            'maneja_vencimiento',
            'metodo_salida',
        ]
        widgets = {
            'codigo_barra': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código de barras'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'precio_costo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'precio_venta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'alicuota_iva': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_actual': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }