import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from app.models import Slide, Message, Alert


class Command(BaseCommand):
    help = 'Remove todos os slides, mensagens e alertas antigos e limpa os arquivos de mídia enviados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-messages',
            action='store_true',
            help='Mantém as mensagens de texto/avisos e apaga apenas os slides/mídias.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando limpeza de conteúdos antigos...'))

        # 1. Apagar Slides do Banco
        slides_count = Slide.objects.count()
        Slide.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ {slides_count} slides removidos do banco de dados.'))

        # 2. Apagar Mensagens (se não indicado para manter)
        if not options['keep_messages']:
            msg_count = Message.objects.count()
            Message.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ {msg_count} mensagens/avisos removidos do banco de dados.'))

        # 3. Limpar Alertas
        alert_count = Alert.objects.count()
        Alert.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ {alert_count} alertas removidos.'))

        # 4. Limpar arquivos físicos de upload em static/uploads, staticfiles/uploads e media
        directories_to_clean = [
            os.path.join(settings.BASE_DIR, 'app', 'static', 'uploads'),
            os.path.join(settings.BASE_DIR, 'staticfiles', 'uploads'),
            os.path.join(settings.BASE_DIR, 'media'),
        ]

        deleted_files_count = 0
        for directory in directories_to_clean:
            if os.path.exists(directory):
                for item in os.listdir(directory):
                    if item in ['.gitkeep', '.gitignore', 'README.md']:
                        continue
                    item_path = os.path.join(directory, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                            deleted_files_count += 1
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                            deleted_files_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Falha ao apagar {item_path}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'✓ {deleted_files_count} arquivos de mídia físicos deletados.'))
        self.stdout.write(self.style.SUCCESS('🎉 Limpeza concluída com sucesso! O sistema está pronto para novos conteúdos.'))
