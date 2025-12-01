from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone
from .utils import clean_rut, is_valid_rut 


# ====================================================================
# CONSTANTES Y CHOICES
# ====================================================================

ROLES_CHOICES = (
    ('super_admin', 'Super Administrador (TemucoSoft)'),
    ('admin_cliente', 'Admin Cliente (Dueño/Suscriptor)'),
    ('gerente', 'Gerente'),
    ('vendedor', 'Vendedor'),
    ('cliente_final', 'Cliente Final (E-commerce)'),
)

ORDER_STATUS_CHOICES = (
    ('pendiente', 'Pendiente'),
    ('enviado', 'Enviado'),
    ('entregado', 'Entregado'),
)

PLAN_CHOICES = (
    ('basico', 'Básico'),
    ('estandar', 'Estándar'),
    ('premium', 'Premium'),
)

# ====================================================================
# GESTIÓN DE CUENTAS, SUSCRIPCIONES Y TENANT
# ====================================================================

class Subscription(models.Model):
    """Define los planes de suscripción (Básico/Estándar/Premium)[cite: 44]."""
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True, default='basico')
    max_users = models.IntegerField(default=1) 
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.get_name_display()


class Company(models.Model):
    """Representa al cliente/tenant[cite: 39]."""
    name = models.CharField(max_length=100)
    rut = models.CharField(max_length=12, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Relación de suscripción: El plan actual de la compañía.
    plan = models.ForeignKey(
        Subscription, 
        on_delete=models.SET_NULL, 
        related_name='companies',
        null=True,
        blank=True
    )
    
    subscription_status = models.CharField(max_length=50, default='activo') 

    def __str__(self):
        return self.name
    
    def clean(self):
        """Validación de RUT."""
        super().clean()
        if self.rut:
            self.rut = clean_rut(self.rut)
            if not is_valid_rut(self.rut):
                raise ValidationError({'rut': "El RUT de la Compañía ingresado no es válido."})


class CustomUser(AbstractUser):
    """Usuario custom (AUTH_USER_MODEL) con control de roles y tenant[cite: 39, 12]."""
    role = models.CharField(max_length=50, choices=ROLES_CHOICES, default='vendedor')
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Solución a los ERRORES de Clashes (related_name)
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=('groups'),
        blank=True,
        related_name='temucosoft_user_groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=('user permissions'),
        blank=True,
        related_name='temucosoft_user_permissions',
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def clean(self):
        """Validación de RUT."""
        super().clean()
        if self.rut:
            self.rut = clean_rut(self.rut)
            if not is_valid_rut(self.rut):
                raise ValidationError({'rut': "El RUT del Usuario ingresado no es válido."})

# ====================================================================
# INVENTARIO Y PROVEEDORES
# ====================================================================

class Product(models.Model):
    """Producto: sku, name, description, price (>=0), cost (>=0), category[cite: 49, 91]."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.price < 0:
            raise ValidationError({'price': "El precio debe ser mayor o igual a cero."})
        if self.cost < 0:
            raise ValidationError({'cost': "El costo debe ser mayor o igual a cero."})

class Branch(models.Model):
    """Sucursal: nombre, dirección, teléfono[cite: 51]."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

class Supplier(models.Model):
    """Proveedor: nombre, rut (validar), contacto[cite: 55]."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    rut = models.CharField(max_length=12, unique=True)
    contact = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.rut:
            self.rut = clean_rut(self.rut)
            if not is_valid_rut(self.rut):
                raise ValidationError({'rut': "El RUT del Proveedor ingresado no es válido."})

class Inventory(models.Model):
    """Relación Branch x Product con stock (>=0), reorder_point[cite: 54, 91]."""
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    stock = models.IntegerField(default=0)
    reorder_point = models.IntegerField(default=5)

    class Meta:
        unique_together = ('branch', 'product')

    def __str__(self):
        return f"{self.product.name} en {self.branch.name}"

    def clean(self):
        super().clean()
        if self.stock < 0:
            raise ValidationError({'stock': "El stock no puede ser negativo."})

# ====================================================================
# TRANSACCIONES Y ÓRDENES
# ====================================================================

class Purchase(models.Model):
    """Orden de entrada de stock desde proveedor[cite: 57, 194]."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    user = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    date = models.DateField(default=timezone.now)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Compra {self.pk} a {self.supplier.name}"

    def clean(self):
        super().clean()
        if self.date > timezone.localdate():
            raise ValidationError({'date': "La fecha de compra no puede ser futura."})

class PurchaseItem(models.Model):
    """Detalle de los productos en una orden de compra."""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

class Sale(models.Model):
    """Transacción de venta en Punto de Venta (POS)[cite: 61, 192]."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    user = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Venta POS {self.pk} - Total: {self.total}"

    def clean(self):
        super().clean()
        if self.created_at > timezone.now():
            raise ValidationError({'created_at': "La fecha de venta no puede ser futura."})

class Order(models.Model):
    """Transacción de venta en E-commerce[cite: 62]."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    client_name = models.CharField(max_length=100)
    client_email = models.EmailField()
    status = models.CharField(max_length=50, choices=ORDER_STATUS_CHOICES, default='pendiente')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Orden E-comm {self.pk} - Cliente: {self.client_name}"

class CartItem(models.Model):
    """Línea de producto en una Sale o Order[cite: 203]."""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def clean(self):
        super().clean()
        if self.quantity < 1:
            raise ValidationError({'quantity': "La cantidad del ítem debe ser mayor o igual a uno."})
