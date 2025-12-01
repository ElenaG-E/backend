# temucosoft_app/management/commands/configure_superuser.py

from django.core.management.base import BaseCommand
from temucosoft_app.models import CustomUser

class Command(BaseCommand):
    help = 'Busca el superusuario existente y le asigna el rol y RUT de super_admin.'

    def handle(self, *args, **kwargs):
        # 1. Usamos el nombre que acabas de crear
        USERNAME_SISTEMA = 'VEPG_superadmin' 

        try:
            # Buscar al usuario por nombre y bandera is_superuser=True
            superuser = CustomUser.objects.get(username=USERNAME_SISTEMA, is_superuser=True)
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Usuario de Sistema encontrado: {USERNAME_SISTEMA}"))
            
            # 2. Asignar el rol correcto
            superuser.role = 'super_admin' # Requerido para la lógica de permiso
            superuser.rut = '19518691-k',
            superuser.is_active = True # Asegurar que la cuenta esté activa
            superuser.save()
            
            self.stdout.write(self.style.SUCCESS(f"🎉 Configuración Exitosa: {superuser.username} es ahora '{superuser.role}'."))

        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"\n❌ ERROR: No se encontró al usuario '{USERNAME_SISTEMA}'."))
            self.stdout.write("Asegúrese de que el nombre de usuario en el script coincida exactamente con el creado.")
            
        except CustomUser.MultipleObjectsReturned:
            self.stdout.write(self.style.ERROR("\n❌ ERROR: Múltiples Superusuarios encontrados. Corrija manualmente."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Ocurrió un error inesperado durante la configuración: {e}"))
