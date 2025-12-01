# temucosoft_drf/urls.py (Proyecto principal)

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from temucosoft_app.views import (
    UserViewSet, CompanyViewSet, ProductViewSet, BranchViewSet, 
    SupplierViewSet, PurchaseViewSet, SaleViewSet, ReportViewSet,  # 👈 Added ReportViewSet
    CartViewSet # 👈 Added CartViewSet for checkout/add
)

# Importa las vistas de templates (para login, dashboard, etc.)
from temucosoft_app import views as template_views

# Inicializa el Router de DRF
router = DefaultRouter()

# =======================================================
# 1. Rutas de la API (DRF Router)
# =======================================================
router.register(r'users', UserViewSet, basename='user')
router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'branches', BranchViewSet, basename='branch')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchases', PurchaseViewSet, basename='purchase')
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'reports', ReportViewSet, basename='report') # 👈 New: Reportes API

# Nota: CartViewSet (para /api/cart/add/ y /api/cart/checkout/) se puede registrar aquí o 
#       manejar como una acción separada, pero lo registramos para simplicidad.
router.register(r'cart', CartViewSet, basename='cart') # 👈 New: Cart/Checkout API


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # =======================================================
    # 2. Autenticación JWT 
    # =======================================================
    # POST /api/token/
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), 
    # POST /api/token/refresh/
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # =======================================================
    # 3. API Endpoints
    # =======================================================
    path('api/', include(router.urls)), 
    
    # =======================================================
    # 4. Rutas de Templates (UI y E-commerce)
    # =======================================================
    
    # A. Login / Logout
    path('login/', template_views.login_view, name='login'),
    path('logout/', template_views.logout_view, name='logout'),

    # B. Dashboard y Template Admin (SuperAdmin)
    path('', template_views.dashboard_view, name='dashboard'), 
    path('admin/create-client/', template_views.create_admin_cliente_view, name='admin_create_client'),

    # C. Shop/E-commerce (Requeridos por la evaluación)
    path('shop/products/', template_views.catalogo_list_view, name='catalogo'),
    
    # 👈 New: Endpoints de Templates requeridos
    path('shop/products/<int:pk>/', template_views.product_detail_view, name='product_detail'),
    path('shop/cart/', template_views.cart_view, name='cart_view'),
]
