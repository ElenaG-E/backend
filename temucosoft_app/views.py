import logging
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required, user_passes_test

from rest_framework import viewsets, mixins, status, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

# Models
from .models import (
    CustomUser, Company, Subscription, Product, Branch, Supplier,
    Inventory, Purchase, PurchaseItem, Sale, CartItem, Order
)

# Serializers
from .serializers import (
    CustomUserCreateSerializer, CustomUserDetailSerializer, CompanySerializer,
    SubscriptionSerializer, ProductSerializer, BranchSerializer, SupplierSerializer,
    InventorySerializer, SaleCreateSerializer, PurchaseCreateSerializer
)

# Permissions
from .permissions import (
    IsSuperAdmin, IsAdminCliente, IsAdminOrGerente, IsVendedor,
    IsSuperAdminOrAdminCliente, IsAuthenticatedAndActive, IsGerente
)

# Forms
from .forms import AdminClienteCreationForm, SessionLoginForm

# Logging
logger = logging.getLogger(__name__)

# ====================================================================
# BASE MULTI-TENANT
# ====================================================================

class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Clase base que implementa el filtrado por compañía."""

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
            raise serializers.ValidationError(
                "Debe estar asociado a una Compañía para realizar esta acción."
            )


# ====================================================================
# 1. GESTIÓN DE USUARIOS Y COMPAÑÍAS
# ====================================================================

class UserViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.CreateModelMixin):
    queryset = CustomUser.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomUserCreateSerializer
        return CustomUserDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsSuperAdminOrAdminCliente()]
        if self.action == 'me':
            return [IsAuthenticatedAndActive()]
        return [IsSuperAdmin()]

    def perform_create(self, serializer):
        creator = self.request.user
        target_role = serializer.validated_data.get('role')
        target_company = serializer.validated_data.get('company')

        if creator.role == 'super_admin':
            if target_role != 'admin_cliente':
                raise serializers.ValidationError({
                    "role": "El Super Admin solo puede crear 'admin_cliente'."
                })
            if not target_company:
                raise serializers.ValidationError({"company": "Debe asignar una Compañía."})

        elif creator.role == 'admin_cliente':
            if target_role not in ['gerente', 'vendedor']:
                raise serializers.ValidationError({
                    "role": "Solo puede crear Gerentes o Vendedores."
                })
            if target_company != creator.company:
                raise serializers.ValidationError({
                    "company": "Solo puede crear usuarios en su Compañía."
                })

        serializer.save()

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = CustomUserDetailSerializer(request.user)
        return Response(serializer.data)


class CompanyViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

    def get_permissions(self):
        if self.action in ['list', 'create', 'subscribe']:
            return [IsSuperAdmin()]
        return [IsAuthenticatedAndActive()]

    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdmin])
    def subscribe(self, request, pk=None):
        company = self.get_object()
        plan_id = request.data.get('plan_id')

        try:
            plan = Subscription.objects.get(pk=plan_id)
        except Subscription.DoesNotExist:
            return Response({'error': 'Plan no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        company.plan = plan
        company.subscription_status = 'activo'
        company.save()

        return Response({"status": "success", "plan": plan.name})


# ====================================================================
# 2. INVENTARIO Y PROVEEDORES
# ====================================================================

class ProductViewSet(BaseCompanyViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrGerente]

    def list(self, request, *args, **kwargs):
        try:
            if not request.user.is_authenticated:
                return Response(ProductSerializer(Product.objects.all(), many=True).data)
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error en ProductViewSet.list: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)


class BranchViewSet(BaseCompanyViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAdminCliente]

    @action(detail=True, methods=['get'], permission_classes=[IsAdminOrGerente])
    def inventory(self, request, pk=None):
        try:
            branch = self.get_object()
            items = Inventory.objects.filter(branch=branch)
            return Response(InventorySerializer(items, many=True).data)
        except Exception as e:
            logger.error(f"Error en BranchViewSet.inventory: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)


class SupplierViewSet(BaseCompanyViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAdminOrGerente]


# ====================================================================
# 3. COMPRAS Y VENTAS
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
        total = 0

        for item in items_data:
            product = get_object_or_404(Product, id=item['product'])

            PurchaseItem.objects.create(
                purchase=purchase,
                product=product,
                quantity=item['quantity'],
                unit_cost=item['unit_cost']
            )

            total += item['quantity'] * item['unit_cost']

            inventory, created = Inventory.objects.get_or_create(
                branch=purchase.branch, product=product, defaults={'stock': 0}
            )
            inventory.stock += item['quantity']
            inventory.save()

        purchase.total = total
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
        total = 0

        for item in items_data:
            product = get_object_or_404(Product, id=item['product'])
            branch = sale.branch
            qty = item['quantity']

            try:
                inventory = Inventory.objects.get(branch=branch, product=product)
            except Inventory.DoesNotExist:
                raise serializers.ValidationError({"stock": f"No existe inventario para {product.name}."})

            if inventory.stock < qty:
                raise serializers.ValidationError({"stock": f"Stock insuficiente ({inventory.stock})."})

            inventory.stock -= qty
            inventory.save()

            CartItem.objects.create(
                sale=sale, product=product, quantity=qty, price=product.price
            )

            total += qty * product.price

        sale.total = total
        sale.save()


# ====================================================================
# 4. CARRITO (E-commerce)
# ====================================================================

class CartViewSet(viewsets.GenericViewSet):
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticatedAndActive]

    @action(detail=False, methods=['post'])
    def add(self, request):
        return Response({"status": "success", "message": "Item added to cart (placeholder)."})

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        return Response({"status": "success", "message": "Checkout complete."})


# ====================================================================
# 5. REPORTES
# ====================================================================

class ReportViewSet(viewsets.GenericViewSet):
    queryset = Inventory.objects.all()
    permission_classes = [IsAdminOrGerente]

    @action(detail=False, methods=['get'])
    def stock(self, request):
        try:
            data = Inventory.objects.filter(branch__company=request.user.company) \
                .values('branch__name', 'product__sku', 'product__name', 'stock', 'reorder_point') \
                .order_by('branch__name', 'product__name')
            return Response(data)
        except Exception as e:
            logger.error(f"Error en ReportViewSet.stock: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def sales(self, request):
        try:
            qs = Sale.objects.filter(company=request.user.company)

            if request.query_params.get('date_from'):
                qs = qs.filter(created_at__gte=request.query_params['date_from'])
            if request.query_params.get('date_to'):
                qs = qs.filter(created_at__lte=request.query_params['date_to'])
            if request.query_params.get('branch'):
                qs = qs.filter(branch_id=request.query_params['branch'])

            data = qs.values('branch__name', 'total', 'created_at', 'user__username', 'payment_method') \
                     .order_by('-created_at')

            return Response(data)
        except Exception as e:
            logger.error(f"Error en ReportViewSet.sales: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=500)


# ====================================================================
# 6. VISTAS DE TEMPLATE (UI)
# ====================================================================

def is_super_admin(user):
    return user.is_authenticated and user.role == 'super_admin'


def login_view(request):
    return auth_views.LoginView.as_view(
        template_name='temucosoft_app/login.html',
        authentication_form=SessionLoginForm
    )(request)


def logout_view(request):
    return auth_views.LogoutView.as_view(next_page=reverse_lazy('login'))(request)


@login_required(login_url=reverse_lazy('login'))
def dashboard_view(request):
    return render(request, 'temucosoft_app/dashboard.html')


def catalogo_list_view(request):
    return render(request, 'temucosoft_app/catalogo.html')


def product_detail_view(request, pk):
    return render(request, 'temucosoft_app/product_detail.html')


def cart_view(request):
    return render(request, 'temucosoft_app/cart_checkout.html')


@user_passes_test(is_super_admin, login_url=reverse_lazy('login'))
def create_admin_cliente_view(request):
    if request.method == 'POST':
        form = AdminClienteCreationForm(request.POST)
        if form.is_valid():
            new_company = Company.objects.create(
                name=form.cleaned_data['company_name'],
                rut=form.cleaned_data['company_rut'],
                is_active=True
            )
            CustomUser.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                role='admin_cliente',
                rut=form.cleaned_data['admin_rut'],
                company=new_company
            )
            messages.success(request, f'Cliente {new_company.name} creado exitosamente.')
            return redirect('dashboard')
    else:
        form = AdminClienteCreationForm()

    return render(request, 'temucosoft_app/admin_create_client.html', {
        'form': form,
        'page_title': 'Creación de Cliente'
    })


# ====================================================================
# NUEVAS VISTAS PLACEHOLDER
# ====================================================================

@login_required(login_url=reverse_lazy('login'))
def supplier_list_view(request):
    return render(request, 'temucosoft_app/supplier_list.html')


@login_required(login_url=reverse_lazy('login'))
def branch_list_view(request):
    return render(request, 'temucosoft_app/branch_list.html')


@login_required(login_url=reverse_lazy('login'))
def branch_inventory_list_view(request):
    return render(request, 'temucosoft_app/branch_inventory_list.html')


@login_required(login_url=reverse_lazy('login'))
def sales_list_view(request):
    return render(request, 'temucosoft_app/sales_list.html')


@login_required(login_url=reverse_lazy('login'))
def pos_sell_view(request):
    return render(request, 'temucosoft_app/pos_sell.html')


# ====================================================================
# API ENDPOINTS SIMPLES
# ====================================================================

@api_view(['GET'])
def health_check(request):
    return Response({"status": "ok"}, status=200)


def subscription_detail_view(request):
    return render(request, 'temucosoft_app/dashboard.html')


def user_management_view(request):
    return render(request, 'temucosoft_app/dashboard.html')
