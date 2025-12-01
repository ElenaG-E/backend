from rest_framework.permissions import BasePermission

# Permiso base que verifica que el usuario esté autenticado y activo [cite: 95]
class IsAuthenticatedAndActive(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_active

# Roles individuales
class IsSuperAdmin(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        return request.user.role == 'super_admin'

class IsAdminCliente(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        return request.user.role == 'admin_cliente'

class IsGerente(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        return request.user.role == 'gerente'

class IsVendedor(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        return request.user.role == 'vendedor'

# Permisos combinados para operaciones CRUD
class IsAdminOrGerente(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        user = request.user
        return user.role in ['admin_cliente', 'gerente']
        
class IsSuperAdminOrAdminCliente(IsAuthenticatedAndActive):
    def has_permission(self, request, view):
        if not super().has_permission(request, view): return False
        return request.user.role in ['super_admin', 'admin_cliente']
