from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from .models import (CustomUser, Company, Subscription, Product, Branch, Supplier, 
    Inventory, Purchase, PurchaseItem, Sale, Order, CartItem, ROLES_CHOICES, ORDER_STATUS_CHOICES
)
from .utils import is_valid_rut, clean_rut

# --- UTILIDADES DE VALIDACIÓN ---

def validate_rut_field(value):
    rut_limpio = clean_rut(value)
    if not rut_limpio or not is_valid_rut(rut_limpio):
        raise serializers.ValidationError("El RUT no es válido o está mal formateado.")
    return rut_limpio

# --- SERIALIZERS DE CUENTAS ---

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'rut', 'is_active', 'plan']
    
    def validate_rut(self, value):
        return validate_rut_field(value)

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'
    
    # La validación de fechas debe ser manejada aquí o en el model
    # def validate(self, data):
    #     start_date = data.get('start_date')
    #     end_date = data.get('end_date')
    #     if start_date and end_date and end_date <= start_date:
    #         raise serializers.ValidationError({"end_date": "La fecha de fin debe ser posterior a la fecha de inicio."})
    #     return data


class CustomUserCreateSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', write_only=True, required=False
    )
    # Password debe ser write_only y validado
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'password', 'role', 'rut', 'company_id']
        
    def validate_rut(self, value):
        return validate_rut_field(value)

    def validate_password(self, value):
        try:
            DjangoValidationError(validate_password(value))
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', 'vendedor'),
            rut=validated_data.get('rut'),
            company=validated_data.get('company')
        )
        return user

class CustomUserDetailSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role', 'rut', 'company_name', 'is_active']

# --- SERIALIZERS DE INVENTARIO ---

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'company', 'sku', 'name', 'description', 'price', 'cost', 'category']
        read_only_fields = ['company']

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'phone', 'company']
        read_only_fields = ['company']

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'rut', 'contact', 'company']
        read_only_fields = ['company']

    def validate_rut(self, value):
        return validate_rut_field(value)

class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = ['branch', 'product', 'stock', 'reorder_point']
        
# --- SERIALIZERS DE TRANSACCIONES ---

class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = ['product', 'quantity', 'unit_cost']

class PurchaseCreateSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, write_only=True)

    class Meta:
        model = Purchase
        fields = ['id', 'supplier', 'branch', 'date', 'items', 'total']
        read_only_fields = ['total', 'user', 'company']

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("La fecha de compra no puede ser futura.")
        return value

class SaleCreateSerializer(serializers.ModelSerializer):
    items = serializers.JSONField() # Usar JSONField para la lista anidada simplifica la estructura

    class Meta:
        model = Sale
        fields = ['id', 'branch', 'payment_method', 'items'] # user y total son asignados en la vista
        read_only_fields = ['user', 'company']
