import ast
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Settings, FeedStatus, Room
from app.utils import get_settings

class Command(BaseCommand):
    help = "Cria/registra os equipamentos e feeds P1EQPT1 até P1EQPT6 no banco de dados."

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Substitui completamente a lista de feeds atual pelos novos equipamentos.',
        )

    def handle(self, *args, **options):
        new_equipments = [f"P1EQPT{i}" for i in range(1, 7)]
        self.stdout.write(self.style.NOTICE(f"Cadastrando equipamentos: {', '.join(new_equipments)}"))

        # 1. Atualizar Settings.feeds
        settings_obj = get_settings()
        try:
            current_feeds = ast.literal_eval(settings_obj.feeds)
            if not isinstance(current_feeds, list):
                current_feeds = []
        except Exception:
            current_feeds = []

        if options['replace']:
            updated_feeds = new_equipments
        else:
            updated_feeds = list(current_feeds)
            for eq in new_equipments:
                if eq not in updated_feeds:
                    updated_feeds.append(eq)

        settings_obj.feeds = str(updated_feeds)
        settings_obj.save()
        self.stdout.write(self.style.SUCCESS(f"✅ Settings.feeds atualizado: {settings_obj.feeds}"))

        # 2. Criar ou atualizar FeedStatus e Room
        for eq in new_equipments:
            fs, created_fs = FeedStatus.objects.get_or_create(
                feed_name=eq,
                defaults={'last_access': timezone.now(), 'is_recently_updated': 1}
            )
            if not created_fs:
                fs.is_recently_updated = 1
                fs.last_access = timezone.now()
                fs.save()

            room, created_room = Room.objects.get_or_create(
                id=eq,
                defaults={'title': f"Equipamento {eq}", 'status': 1}
            )

            status_str = "criado" if created_fs else "atualizado"
            self.stdout.write(self.style.SUCCESS(f" - [{eq}] FeedStatus e Room ({status_str}) com sucesso."))

        self.stdout.write(self.style.SUCCESS("\n🎉 Todos os equipamentos P1EQPT1 até P1EQPT6 foram criados e estão prontos para uso!"))
