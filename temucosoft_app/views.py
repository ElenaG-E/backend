from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction, models
from django.urls import reverse_lazy
from django.utils import timezone
import datetime # Necesario para la lógica de fechas en reportes

# Importaciones de Modelos
from .models import (CustomUser, Company, Subscription, Product, Branch, Supplier, 
    Inventory, Purchase, PurchaseItem, Sale, CartItem, Order)

# Importaciones de Serializers
from .serializers import (
    CustomUserCreateSerializer, CustomUserDetailSerializer, CompanySerializer, 
    SubscriptionSerializer, ProductSerializer, BranchSerializer, SupplierSerializer, 
    InventorySerializer, SaleCreateSerializer, PurchaseCreateSerializer
)

# Importaciones de Permisos
from .permissions import (IsSuperAdmin, IsAdminCliente, IsAdminOrGerente, IsVendedor, 
    IsSuperAdminOrAdminCliente, IsAuthenticatedAndActive, IsGerente)

# Importaciones de Forms y Auth (para vistas de Templates)
from .forms import AdminClienteCreationForm, SessionLoginForm 
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages


# ====================================================================
# BASE VIEWS PARA MULTI-TENANT
# ====================================================================

class BaseCompanyViewSet(viewsets.ModelViewSet):
    # ... (código BaseCompanyViewSet) ...
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            if user.role == 'super_admin':
                return self.queryset.all()
            if user.company:
                return self.queryset.filter(company=user.company)
        return self.queryset.none()
    
    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and user.company:
            serializer.save(company=user.company)
        else:
            raise serializers.ValidationError("Debe estar asociado a una Compañía para realizar esta acción.")

# ====================================================================
# 1. GESTIÓN DE USUARIOS Y COMPAÑÍAS (APIs)
# ====================================================================

class UserViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.CreateModelMixin):
    queryset = CustomUser.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomUserCreateSerializer
        return CustomUserDetailSerializer

    def get_permissions(self):
        if self.action == 'create': return [IsSuperAdminOrAdminCliente()] 
        if self.action == 'me': return [IsAuthenticatedAndActive()]
        return [IsSuperAdmin()] 

    def perform_create(self, serializer):
        creator = self.request.user
        target_role = serializer.validated_data.get('role')
        target_company = serializer.validated_data.get('company')

        if creator.role == 'super_admin':
            if target_role != 'admin_cliente':
                raise serializers.ValidationError({"role": "El Super Admin solo puede crear el rol 'admin_cliente'."})
            if not target_company:
                 raise serializers.ValidationError({"company": "El Super Admin debe asignar una Compañía válida."})

        elif creator.role == 'admin_cliente':
            if target_role not in ['gerente', 'vendedor']:
                raise serializers.ValidationError({"role": "El Admin Cliente solo puede crear Gerentes o Vendedores."})
            
            if target_company != creator.company:
                 raise serializers.ValidationError({"company": "Solo puede crear usuarios en su propia Compañía."})
                 
        serializer.save()

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        serializer = CustomUserDetailSerializer(request.user)
        return Response(serializer.data)


class CompanyViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

    def get_permissions(self):
        if self.action in ['list', 'create', 'subscribe']: return [IsSuperAdmin()]
        return [IsAuthenticatedAndActive()]

    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdmin])
    def subscribe(self, request, pk=None):
        company = self.get_object()
        plan_id = request.data.get('plan_id')
        
        try:
            plan = Subscription.objects.get(pk=plan_id)
        except Subscription.DoesNotExist:
            return Response({'error': 'Plan de suscripción no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        
        company.plan = plan
        company.subscription_status = 'activo'
        company.save()
        
        return Response({"status": "success", "plan": plan.name}, status=status.HTTP_200_OK)


# ====================================================================
# 2. INVENTARIO Y PROVEEDORES (APIs)
# ====================================================================

class ProductViewSet(BaseCompanyViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrGerente]
    
    def list(self, request, *args, **kwargs):
        # Permite lectura pública para el catálogo (si no hay autenticación)
        if not request.user.is_authenticated:
            queryset = Product.objects.all() 
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        
        return super().list(request, *args, **kwargs)


class BranchViewSet(BaseCompanyViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAdminCliente]

    @action(detail=True, methods=['get'], permission_classes=[IsAdminOrGerente])
    def inventory(self, request, pk=None):
        branch = self.get_object()
        inventory_items = Inventory.objects.filter(branch=branch)
        serializer = InventorySerializer(inventory_items, many=True)
        return Response(serializer.data)


class SupplierViewSet(BaseCompanyViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAdminOrGerente]


# ====================================================================
# 3. TRANSACCIONES Y MOVIMIENTOS DE STOCK (APIs)
# ====================================================================

class PurchaseViewSet(BaseCompanyViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseCreateSerializer
    permission_classes = [IsGerente]

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        items_data = self.request.data.get('items', [])
        
        purchase = serializer.save(user=user, company=user.company, total=0) 
        total_compra = 0
        
        for item_data in items_data:
            product = get_object_or_404(Product, id=item_data['product'])
            
            PurchaseItem.objects.create(
                purchase=purchase, product=product, quantity=item_data['quantity'],
                unit_cost=item_data['unit_cost']
            )
            total_compra += item_data['quantity'] * item_data['unit_cost']
            
            inventory, created = Inventory.objects.get_or_create(
                branch=purchase.branch, product=product, defaults={'stock': 0}
            )
            inventory.stock += item_data['quantity']
            inventory.save()
            
        purchase.total = total_compra
        purchase.save()


class SaleViewSet(BaseCompanyViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleCreateSerializer
    permission_classes = [IsVendedor]

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        items_data = self.request.data.get('items', [])
        
        sale = serializer.save(user=user, company=user.company, total=0)
        total_venta = 0

        for item_data in items_data:
            product = get_object_or_404(Product, id=item_data['product'])
            branch = sale.branch 
            quantity_sold = item_data['quantity']
            
            try:
                inventory = Inventory.objects.get(branch=branch, product=product)
            except Inventory.DoesNotExist:
                raise serializers.ValidationError({"stock": f"Producto {product.name} no registrado en inventario de {branch.name}."})

            if inventory.stock < quantity_sold:
                raise serializers.ValidationError({"stock": f"Stock insuficiente (Actual: {inventory.stock}) para {product.name}."})

            inventory.stock -= quantity_sold
            inventory.save()

            CartItem.objects.create(
                sale=sale, product=product, quantity=quantity_sold,
                price=product.price 
            )
            total_venta += quantity_sold * product.price

        sale.total = total_venta
        sale.save()

# --- NUEVO VIEWSET: GESTIÓN DE CARRITO (E-commerce) ---

class CartViewSet(viewsets.GenericViewSet):
    """
    Gestiona la lógica de agregar ítems al carrito y el proceso de checkout.
    """
    queryset = Order.objects.all() 
    permission_classes = [IsAuthenticatedAndActive] 

    @action(detail=False, methods=['post'])
    def add(self, request):
        return Response({"status": "success", "message": "Item added to cart (placeholder)."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def checkout(self, request):
        # Placeholder para la funcionalidad.
        return Response({"status": "success", "message": "Checkout complete. Order created (placeholder)."}, status=status.HTTP_201_CREATED)


# ====================================================================
# 4. REPORTES (APIs)
# ====================================================================

class ReportViewSet(viewsets.GenericViewSet):
    queryset = Inventory.objects.all() 
    permission_classes = [IsAdminOrGerente] 

    @action(detail=False, methods=['get'])
    def stock(self, request):
        stock_report = Inventory.objects.filter(branch__company=request.user.company).values(
            'branch__name', 'product__sku', 'product__name', 'stock', 'reorder_point'
        ).order_by('branch__name', 'product__name')
        
        return Response(stock_report, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def sales(self, request):
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        branch_id = request.query_params.get('branch')
        
        sales_query = Sale.objects.filter(company=request.user.company)
        
        if date_from_str:
            sales_query = sales_query.filter(created_at__gte=date_from_str)
        if date_to_str:
            sales_query = sales_query.filter(created_at__lte=date_to_str)
        if branch_id:
            sales_query = sales_query.filter(branch_id=branch_id)
            
        report_data = sales_query.values(
            'branch__name', 'total', 'created_at', 'user__username', 'payment_method'
        ).order_by('-created_at')

        return Response(report_data, status=status.HTTP_200_OK)


# ====================================================================
# 5. VISTAS BASADAS EN TEMPLATES (UI)
# ====================================================================

def is_super_admin(user):
    return user.is_authenticated and user.role == 'super_admin'

def login_view(request):
    return auth_views.LoginView.as_view(template_name='temucosoft_app/login.html', authentication_form=SessionLoginForm)(request)

def logout_view(request):
    return auth_views.LogoutView.as_view(next_page=reverse_lazy('login'))(request)

@login_required(login_url=reverse_lazy('login'))
def dashboard_view(request):
    return render(request, 'temucosoft_app/dashboard.html')

def catalogo_list_view(request):
    return render(request, 'temucosoft_app/catalogo.html')

def product_detail_view(request, pk):
    # Placeholder para el detalle de producto
    return render(request, 'temucosoft_app/product_detail.html')

def cart_view(request):
    # Placeholder para la vista del carrito
    return render(request, 'temucosoft_app/cart_checkout.html')

@user_passes_test(is_super_admin, login_url=reverse_lazy('login'))
def create_admin_cliente_view(request):
    if request.method == 'POST':
        form = AdminClienteCreationForm(request.POST)
        if form.is_valid():
            new_company = Company.objects.create(
                name=form.cleaned_data['company_name'], rut=form.cleaned_data['company_rut'], is_active=True
            )
            CustomUser.objects.create_user(
                username=form.cleaned_data['username'], email=form.cleaned_data['email'],
                password=form.cleaned_data['password'], role='admin_cliente', rut=form.cleaned_data['admin_rut'],
                company=new_company
            )
            messages.success(request, f'Cuenta de Cliente {new_company.name} creada con éxito.')
            return redirect('dashboard')
    else:
        form = AdminClienteCreationForm()
        
    context = {'form': form, 'page_title': 'Creación de Cliente'}
    return render(request, 'temucosoft_app/admin_create_client.html', context)
