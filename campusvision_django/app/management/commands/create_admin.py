from django.core.management.base import BaseCommand
from app.models import User

class Command(BaseCommand):
    help = 'Cria ou atualiza um usuario com privilegios de Administrador'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='E-mail do administrador')
        parser.add_argument('--name', type=str, help='Nome do administrador')
        parser.add_argument('--password', type=str, help='Senha de acesso')

    def handle(self, *args, **options):
        email = options.get('email')
        name = options.get('name')
        password = options.get('password')

        if not email:
            email = input('Digite o E-mail: ').strip()
        if not name:
            name = input('Digite o Nome: ').strip()
        if not password:
            password = input('Digite a Senha: ').strip()

        if not email or not password:
            self.stdout.write(self.style.ERROR('E-mail e senha sao obrigatorios.'))
            return

        user, created = User.objects.get_or_create(email=email)
        user.name = name or 'Administrador'
        user.is_admin = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f'[OK] Administrador "{email}" criado com sucesso!'))
        else:
            self.stdout.write(self.style.SUCCESS(f'[OK] Usuario "{email}" atualizado para Administrador com sucesso!'))
