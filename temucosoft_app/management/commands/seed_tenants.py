# temucosoft_app/management/commands/seed_tenants.py

from django.core.management.base import BaseCommand
from temucosoft_app.models import Company, CustomUser, Subscription
import sys

class Command(BaseCommand):
    help = 'Crea los planes de suscripción y las tres tiendas de prueba con sus administradores.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Iniciando Seeding de Tenants y Administradores ---'))

        # --- 1. Definición de Planes ---
        
        # Primero, asegúrate de que los planes Básico, Estándar, y Premium existan.
        self.stdout.write("1. Creando/Verificando Planes de Suscripción...")
        
        plan_basico, _ = Subscription.objects.get_or_create(
            name='basico',
            defaults={'max_users': 3, 'price': 9.99, 'description': 'Plan Básico'}
        )
        plan_estandar, _ = Subscription.objects.get_or_create(
            name='estandar',
            defaults={'max_users': 10, 'price': 29.99, 'description': 'Plan Estándar'}
        )
        plan_premium, _ = Subscription.objects.get_or_create(
            name='premium',
            defaults={'max_users': 999, 'price': 99.99, 'description': 'Plan Premium'}
        )
        
        PLANS = {
            'FULL': plan_premium,
            'MEDIO': plan_estandar,
            'BÁSICO': plan_basico,
        }
        
        # --- 2. Definición de Datos de Prueba ---

        TIENDAS_ADMINISTRADORES = [
            {
                'tienda_name': "Tienda Mayorista FULL",
                'rut_company': '99776655-4',
                'plan_obj': PLANS['FULL'],
                'admin_username': 'admin_full',
                'admin_rut': '10101010-1',
                'password': '1234'
            },
            {
                'tienda_name': "Supermercado MEDIO",
                'rut_company': '88554433-2',
                'plan_obj': PLANS['MEDIO'],
                'admin_username': 'admin_medio',
                'admin_rut': '20202020-2',
                'password': '1234'
            },
            {
                'tienda_name': "Farmacia BÁSICA",
                'rut_company': '11223344-5',
                'plan_obj': PLANS['BÁSICO'],
                'admin_username': 'admin_basico',
                'admin_rut': '30303030-3',
                'password': '1234'
            },
        ]
        
        # --- 3. Lógica de Creación e Iteración ---
        
        self.stdout.write("\n2. Creando Tiendas (Company) y Administradores (CustomUser)...")
        
        for datos in TIENDAS_ADMINISTRADORES:
            # 3.1 Obtener/Crear la Compañía (Tenant)
            tienda, created_t = Company.objects.update_or_create(
                name=datos['tienda_name'],
                defaults={
                    'rut': datos['rut_company'],
                    'plan': datos['plan_obj'],
                    'is_active': True,
                    'subscription_status': 'activo'
                }
            )

            # 3.2 Obtener/Crear el Admin Cliente
            admin_user, created_a = CustomUser.objects.update_or_create(
                username=datos['admin_username'],
                defaults={
                    'email': f"{datos['admin_username']}@tienda.com",
                    'role': 'admin_cliente',
                    'rut': datos['admin_rut'],
                    'company': tienda,
                    'is_active': True
                }
            )

            # 3.3 Setear la contraseña solo si el usuario fue creado
            if created_a:
                admin_user.set_password(datos['password'])
                admin_user.save()
                self.stdout.write(self.style.SUCCESS(f"   -> ✅ Creado Admin: {admin_user.username} para {tienda.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"   -> ℹ️ Existe Admin: {admin_user.username}"))
        
        self.stdout.write(self.style.SUCCESS("\n🎉 Proceso de Seeding completado con éxito."))
