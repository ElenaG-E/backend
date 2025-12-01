# temucosoft_app/permissions.py

from rest_framework.permissions import BasePermission

# Permiso base que verifica que el usuario esté autenticado y activo
class IsAuthenticatedAndActive(BasePermission):
    """
    Permite acceso solo si el usuario está autenticado y su cuenta está activa.
    """
    def has_permission(self, request, view):
        # is_active debe ser verificado antes de permitir el acceso.
        return request.user and request.user.is_authenticated and request.user.is_active

# 1. Rol super_admin (Configura clientes, planes) [cite: 17]
class IsSuperAdmin(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role == 'super_admin'

# 2. Rol admin_cliente (Administra todo en su tenant) [cite: 18, 19]
class IsAdminCliente(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role == 'admin_cliente'

# 3. Rol gerente (Gestión de inventario, reportes, proveedores) [cite: 20]
class IsGerente(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role == 'gerente'

# 4. Rol vendedor (Realiza ventas POS, no cambia precios) [cite: 24]
class IsVendedor(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role == 'vendedor'

# Permisos Combinados (convenientes para ciertas operaciones de CRUD)
class IsAdminOrGerente(IsAuthenticatedAndActive):
    """Permite acceso a admin_cliente o gerente (CRUD de Productos/Inventario)."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return user.role in ['admin_cliente', 'gerente']

class IsAdminOrGerenteOrVendedor(IsAuthenticatedAndActive):
    """Permite acceso a todos los empleados."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return user.role in ['admin_cliente', 'gerente', 'vendedor']
