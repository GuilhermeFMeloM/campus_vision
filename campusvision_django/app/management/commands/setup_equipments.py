import ast
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Settings, FeedStatus, Room
from app.utils import get_settings

class Command(BaseCommand):
    help = "Cria/registra os equipamentos (P1EQPT1..P1EQPT6 com notícias e P0MIDIAS1..P0MIDIAS3 em modo Embed sem notícias)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Substitui completamente a lista de feeds atual pelos novos equipamentos.',
        )

    def handle(self, *args, **options):
        # Definição dos equipamentos e seus comportamentos
        # P1EQPT1 a P1EQPT6: Notícias Ativas (show_news = True)
        # P0MIDIAS1 a P0MIDIAS3: Modo Embed / Sem Notícias (show_news = False)
        equipments_config = [
            ("P1EQPT1", True),
            ("P1EQPT2", True),
            ("P1EQPT3", True),
            ("P1EQPT4", True),
            ("P1EQPT5", True),
            ("P1EQPT6", True),
            ("P0MIDIAS1", False),
            ("P0MIDIAS2", False),
            ("P0MIDIAS3", False),
        ]

        all_equipment_names = [eq[0] for eq in equipments_config]
        self.stdout.write(self.style.NOTICE(f"Configurando equipamentos: {', '.join(all_equipment_names)}"))

        # 1. Atualizar Settings.feeds
        settings_obj = get_settings()
        try:
            current_feeds = ast.literal_eval(settings_obj.feeds)
            if not isinstance(current_feeds, list):
                current_feeds = []
        except Exception:
            current_feeds = []

        if options['replace']:
            updated_feeds = all_equipment_names
        else:
            updated_feeds = list(current_feeds)
            for eq_name in all_equipment_names:
                if eq_name not in updated_feeds:
                    updated_feeds.append(eq_name)

        settings_obj.feeds = str(updated_feeds)
        settings_obj.save()
        self.stdout.write(self.style.SUCCESS(f"✅ Settings.feeds atualizado: {settings_obj.feeds}"))

        # 2. Criar ou atualizar FeedStatus e Room para cada equipamento
        for eq_name, enable_news in equipments_config:
            fs, created_fs = FeedStatus.objects.get_or_create(
                feed_name=eq_name,
                defaults={
                    'last_access': timezone.now(),
                    'is_recently_updated': 1,
                    'show_news': enable_news
                }
            )
            if not created_fs:
                # Mantém ou atualiza flag se for os P0MIDIAS
                if not enable_news:
                    fs.show_news = False
                fs.is_recently_updated = 1
                fs.last_access = timezone.now()
                fs.save()

            room, created_room = Room.objects.get_or_create(
                id=eq_name,
                defaults={'title': f"Equipamento {eq_name}", 'status': 1}
            )

            news_status_str = "Com Notícias" if fs.show_news else "Sem Notícias (Modo Embed)"
            status_str = "criado" if created_fs else "atualizado"
            self.stdout.write(self.style.SUCCESS(f" - [{eq_name}] FeedStatus e Room ({status_str}) -> {news_status_str}"))

        self.stdout.write(self.style.SUCCESS("\n🎉 Todos os equipamentos (P1EQPT1..P1EQPT6 e P0MIDIAS1..P0MIDIAS3) configurados com sucesso!"))
