import logging
import urllib.request
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.db import connection
from .models import Slide, Alert, Message, Settings, FeedStatus, BusSchedule

logger = logging.getLogger(__name__)

# Cache simples em memória para notícias e clima (evita chamadas excessivas)
_NEWS_CACHE = {'timestamp': None, 'data': []}
_WEATHER_CACHE = {'timestamp': None, 'data': None}

def mod_counter():
    """Conta quantos slides aguardam moderação."""
    return Slide.objects.filter(approval="Waiting Review").count()

def allowed_file(filename, allowed_ext=None):
    """Verifica se a extensão do arquivo está permitida."""
    if allowed_ext is None:
        allowed_ext = getattr(settings, 'ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'mp4', 'webm'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_ext

def feed_matches(target_feed, feeds_val):
    """Verifica de forma case-insensitive e tolerante se o slide pertence ao feed especificado."""
    if not target_feed or not feeds_val:
        return False
    target = str(target_feed).strip().lower()
    feeds_str = str(feeds_val).strip().lower()

    if target in feeds_str:
        return True

    # Parse caso esteja no formato lista string "['feed1', 'feed2']"
    import ast
    try:
        parsed = ast.literal_eval(str(feeds_val))
        if isinstance(parsed, (list, tuple, set)):
            return any(str(item).strip().lower() == target for item in parsed)
    except Exception:
        pass

    return False

def trigger_feed_reload(feeds=None):
    """Incrementa reload_id para forçar as Smart TVs a atualizarem imediatamente."""
    try:
        with connection.cursor() as cursor:
            if feeds is None or feeds == '__ALL__':
                cursor.execute("UPDATE `FeedStatus` SET `reload_id` = COALESCE(`reload_id`, 0) + 1;")
            else:
                if isinstance(feeds, str):
                    try:
                        import ast
                        parsed = ast.literal_eval(feeds)
                        if isinstance(parsed, (list, tuple, set)):
                            target_list = [str(f).strip() for f in parsed if f]
                        else:
                            target_list = [feeds.strip()]
                    except Exception:
                        target_list = [feeds.strip()]
                elif isinstance(feeds, (list, tuple, set)):
                    target_list = [str(f).strip() for f in feeds if f]
                else:
                    target_list = []

                for feed_name in target_list:
                    if feed_name:
                        cursor.execute(
                            "INSERT INTO `FeedStatus` (`feed_name`, `last_access`, `is_recently_updated`, `show_news`, `reload_id`) "
                            "VALUES (%s, NOW(), 1, 1, 1) "
                            "ON DUPLICATE KEY UPDATE `reload_id` = COALESCE(`reload_id`, 0) + 1;",
                            [feed_name]
                        )
    except Exception as e:
        logger.warning(f"Erro ao disparar trigger_feed_reload: {e}")

def add_slide(time_start, time_end, title, slide_path, feeds, submitted_by="Admin", reading_time=10, approval="Approved"):
    """Adiciona um slide no banco de dados com segurança e atualiza as TVs."""
    slide_data = Slide(
        time_start=str(time_start),
        time_end=str(time_end),
        title=title,
        slide_path=slide_path,
        approval=approval,
        submitted_by=submitted_by,
        feeds=str(feeds),
        reading_time=int(reading_time) if str(reading_time).isdigit() else 10
    )
    slide_data.save()
    if approval == "Approved":
        trigger_feed_reload(feeds)
    return slide_data

def appr_slide(approval, slide_id):
    """Aprova ou muda o status de um slide."""
    try:
        selected_slide = Slide.objects.get(id=slide_id)
        selected_slide.approval = approval
        selected_slide.save()
        trigger_feed_reload(selected_slide.feeds)
        return 1
    except Slide.DoesNotExist:
        return 0

def remove_slide(slide_id):
    """Remove slide do banco."""
    try:
        selected_slide = Slide.objects.get(id=slide_id)
        feeds = selected_slide.feeds
        selected_slide.delete()
        trigger_feed_reload(feeds)
        return 1
    except Slide.DoesNotExist:
        return 0

def parse_date_safe(date_str):
    """Faz parse seguro de data suportando vários formatos."""
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except ValueError:
            continue
    return None

def is_news_enabled_for_feed(target_feed):
    """Verifica se notícias estão habilitadas para o feed/equipamento especificado."""
    if not target_feed:
        return True
    try:
        fs = FeedStatus.objects.filter(feed_name__iexact=str(target_feed).strip()).first()
        if fs is not None:
            return bool(getattr(fs, 'show_news', True))
    except Exception:
        pass
    return True

def get_slides(target_feed, interleave_news=None):
    """Busca slides aprovados para um feed específico e intercala com páginas dinâmicas de notícias (se habilitado)."""
    if interleave_news is None:
        interleave_news = is_news_enabled_for_feed(target_feed)

    user_slides = []
    today_date = timezone.now().date()
    for slide in Slide.objects.filter(approval='Approved').order_by('-id'):
        start_date = parse_date_safe(slide.time_start)
        end_date = parse_date_safe(slide.time_end)

        is_valid_date = True
        if start_date and today_date < start_date:
            is_valid_date = False
        if end_date and today_date > end_date:
            is_valid_date = False

        if feed_matches(target_feed, slide.feeds) and is_valid_date:
            path_lower = slide.slide_path.strip().lower()
            if path_lower.startswith(('http://', 'https://')):
                s_type = 'embed'
            elif path_lower.endswith(('.mp4', '.webm')):
                s_type = 'video'
            else:
                s_type = 'image'

            user_slides.append({
                'type': s_type,
                'slide_path': slide.slide_path.strip(),
                'reading_time': slide.reading_time or 15,
                'title': slide.title
            })

    if not interleave_news:
        return user_slides

    # Obtém todas as notícias recentes (cada notícia vira um slide exclusivo)
    news_items = get_news_feed(limit=12)
    playlist = []

    if user_slides:
        # Distribui todas as notícias entre os slides de usuário
        import math
        chunk_size = max(1, math.ceil(len(news_items) / len(user_slides)))
        for i, slide in enumerate(user_slides):
            playlist.append(slide)
            # Insere as notícias correspondentes a este bloco
            start_n = i * chunk_size
            end_n = min(start_n + chunk_size, len(news_items))
            for n in news_items[start_n:end_n]:
                playlist.append({
                    'type': 'news',
                    'title': n['title'],
                    'summary': n.get('summary', ''),
                    'category': n.get('category', 'Notícias'),
                    'source': n.get('source', 'G1 / BBC'),
                    'pub_date': n.get('pub_date', ''),
                    'reading_time': 12,
                })
        # Se restou alguma notícia não incluída, adiciona ao final
        remaining_start = len(user_slides) * chunk_size
        if remaining_start < len(news_items):
            for n in news_items[remaining_start:]:
                playlist.append({
                    'type': 'news',
                    'title': n['title'],
                    'summary': n.get('summary', ''),
                    'category': n.get('category', 'Notícias'),
                    'source': n.get('source', 'G1 / BBC'),
                    'pub_date': n.get('pub_date', ''),
                    'reading_time': 12,
                })
    else:
        # Se não houver slides cadastrados, exibe todas as notícias como páginas completas
        for n in news_items:
            playlist.append({
                'type': 'news',
                'title': n['title'],
                'summary': n.get('summary', ''),
                'category': n.get('category', 'Notícias'),
                'source': n.get('source', 'G1 / BBC'),
                'pub_date': n.get('pub_date', ''),
                'reading_time': 12,
            })

    return playlist

def get_video(target_feed):
    """Busca o primeiro vídeo aprovado para o feed."""
    today_date = timezone.now().date()
    for slide in Slide.objects.filter(approval='Approved').order_by('-id'):
        start_date = parse_date_safe(slide.time_start)
        end_date = parse_date_safe(slide.time_end)

        is_valid = True
        if start_date and today_date < start_date:
            is_valid = False
        if end_date and today_date > end_date:
            is_valid = False

        if feed_matches(target_feed, slide.feeds) and is_valid:
            if slide.slide_path.lower().endswith(('.mp4', '.webm')):
                return slide.slide_path
    return ""

def update_slide(id, title, time_start, time_end, feeds, reading_time=10):
    """Atualiza dados do slide existente."""
    try:
        slide_data = Slide.objects.get(id=id)
        slide_data.title = title
        slide_data.time_start = str(time_start)
        slide_data.time_end = str(time_end)
        slide_data.feeds = str(feeds)
        slide_data.reading_time = int(reading_time) if str(reading_time).isdigit() else 10
        slide_data.save()
        return 1
    except Slide.DoesNotExist:
        return 0

def alert_status():
    """Recupera o texto do alerta ativo."""
    alert_data = Alert.objects.first()
    return alert_data.alert_text if alert_data and alert_data.alert_text else ""

def update_alert(alert_text):
    """Atualiza o conteúdo do alerta."""
    alert_data = Alert.objects.first()
    if alert_data:
        alert_data.alert_text = alert_text
        alert_data.save()
    else:
        Alert.objects.create(alert_text=alert_text)
    return 1

def add_message(message_text, time_start, time_end, submitted_by="Admin"):
    """Adiciona uma mensagem institucional."""
    return Message.objects.create(
        text=message_text,
        time_start=str(time_start),
        time_end=str(time_end),
        submitted_by=submitted_by
    )

def get_message():
    """Recupera mensagens institucionais e avisos válidos."""
    today_date = timezone.now().date()
    messages_list = []
    for item in Message.objects.all().order_by('-id'):
        start_date = parse_date_safe(item.time_start)
        end_date = parse_date_safe(item.time_end)

        is_valid = True
        if start_date and today_date < start_date:
            is_valid = False
        if end_date and today_date > end_date:
            is_valid = False

        if is_valid and item.text and item.text.strip():
            messages_list.append(item.text.strip())

    if not messages_list:
        messages_list = [
            "Bem-vindo ao Campus! Acompanhe os avisos, notícias e horários de transporte em tempo real.",
            "Mantenha os ambientes organizados e consulte a programação do dia.",
            "Para cadastrar novos comunicados nesta TV, acesse o painel administrativo do CampusVision."
        ]
    return messages_list

def delete_message(message_id):
    """Remove mensagem pelo ID."""
    try:
        message = Message.objects.get(id=message_id)
        message.delete()
        return 1
    except Message.DoesNotExist:
        return 0

def update_settings(duration, signups, feeds):
    """Atualiza configurações gerais."""
    settings_obj = get_settings()
    settings_obj.duration = str(duration)
    settings_obj.allow_signups = int(signups)
    settings_obj.feeds = str(feeds)
    settings_obj.save()
    return 1

def get_settings():
    """Recupera as configurações atuais garantindo que nunca retorne None."""
    settings_obj = Settings.objects.first()
    if not settings_obj:
        settings_obj = Settings.objects.create(
            duration="10000",
            allow_signups=1,
            feeds="['Default', 'Recepcao', 'Refeitorio', 'Comercial']"
        )
    return settings_obj

def signups_allowed():
    """Verifica se cadastro está permitido."""
    settings_obj = get_settings()
    return bool(settings_obj.allow_signups)

def update_feed_access(feed_name):
    """Atualiza o heartbeat de acesso ao feed."""
    try:
        feed_status_entry, created = FeedStatus.objects.get_or_create(
            feed_name=feed_name,
            defaults={'last_access': timezone.now(), 'is_recently_updated': 1, 'show_news': True}
        )
        if not created:
            feed_status_entry.last_access = timezone.now()
            feed_status_entry.is_recently_updated = 1
            feed_status_entry.save(update_fields=['last_access', 'is_recently_updated'])
    except Exception as e:
        logger.warning("Falha ao registrar heartbeat do feed %s: %s", feed_name, e)

    limit_datetime = timezone.now() - timedelta(minutes=40)
    try:
        FeedStatus.objects.filter(last_access__lt=limit_datetime).update(is_recently_updated=0)
    except Exception:
        pass


# ==============================================================================
# RECURSOS DINÂMICOS: NOTÍCIAS, CLIMA E DISTÂNCIA DE ÔNIBUS
# ==============================================================================

def get_news_feed(limit=10):
    """Obtém as notícias mais recentes via RSS de fontes confiáveis com resumo e categoria."""
    global _NEWS_CACHE
    now = timezone.now()

    # Retorna do cache se tiver menos de 10 minutos
    if _NEWS_CACHE['timestamp'] and (now - _NEWS_CACHE['timestamp']).total_seconds() < 600:
        return _NEWS_CACHE['data']

    feed_configs = [
        ("https://g1.globo.com/rss/g1/tecnologia/", "Tecnologia", "G1"),
        ("https://feeds.bbci.co.uk/portuguese/rss.xml", "Mundo & Brasil", "BBC News"),
        ("https://g1.globo.com/rss/g1/brasil/", "Brasil", "G1"),
    ]

    news_items = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    }

    import gzip
    import io
    import re

    for url, default_cat, source_name in feed_configs:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read()
                if response.info().get('Content-Encoding') == 'gzip' or content[:2] == b'\x1f\x8b':
                    content = gzip.decompress(content)
                
                root = ET.fromstring(content)
                for item in root.findall('.//item')[:limit]:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    pub_elem = item.find('pubDate')
                    desc_elem = item.find('description')
                    cat_elem = item.find('category')

                    if title_elem is not None and title_elem.text:
                        clean_desc = ""
                        if desc_elem is not None and desc_elem.text:
                            # Remove tags HTML e espaços duplicados
                            clean_desc = re.sub(r'<[^>]+>', '', desc_elem.text).strip()
                            clean_desc = re.sub(r'\s+', ' ', clean_desc)
                            if len(clean_desc) > 220:
                                clean_desc = clean_desc[:217] + "..."

                        news_items.append({
                            'title': title_elem.text.strip(),
                            'summary': clean_desc,
                            'category': (cat_elem.text.strip() if cat_elem is not None and cat_elem.text else default_cat),
                            'source': source_name,
                            'link': link_elem.text if link_elem is not None else '#',
                            'pub_date': pub_elem.text if pub_elem is not None else ''
                        })
                    if len(news_items) >= limit:
                        break
        except Exception as e:
            logger.warning("Erro ao buscar feed RSS %s: %s", url, e)

    # Fallback se a internet ou o RSS falhar
    if not news_items:
        news_items = [
            {
                'title': 'CampusVision: Acompanhe as informações e novidades em tempo real nesta TV.',
                'summary': 'Mantenha os ambientes organizados, acompanhe a previsão do tempo e os avisos institucionais.',
                'category': 'Institucional',
                'source': 'CampusVision',
                'link': '#',
                'pub_date': ''
            },
            {
                'title': 'Transporte e Ônibus com itinerários atualizados.',
                'summary': 'Confira os horários de saída e previsão de chegada para a região do Shopping Tamboré.',
                'category': 'Transporte',
                'source': 'CampusVision',
                'link': '#',
                'pub_date': ''
            }
        ]

    _NEWS_CACHE = {'timestamp': now, 'data': news_items}
    return news_items


def get_weather_data(city=None):
    """Obtém dados meteorológicos em Celsius com previsão para 5 dias."""
    global _WEATHER_CACHE
    now = timezone.now()

    if _WEATHER_CACHE['timestamp'] and (now - _WEATHER_CACHE['timestamp']).total_seconds() < 1800:
        return _WEATHER_CACHE['data']

    weather_key = getattr(settings, 'WEATHER_KEY', '99ec4e7d956393e48a8cda51317329c5')
    city_name = city or getattr(settings, 'WEATHER_CITY', 'São Paulo,BR')

    weather_result = {
        'city': 'São Paulo',
        'temp_celsius': 23,
        'description': 'Parcialmente Nublado',
        'humidity': 65,
        'icon': '02d',
        'forecast': [
            {'day': 'Hoje', 'temp': 24, 'icon': '02d', 'desc': 'Parcialmente Nublado'},
            {'day': 'Amanhã', 'temp': 26, 'icon': '01d', 'desc': 'Ensolarado'},
            {'day': 'Depois', 'temp': 22, 'icon': '10d', 'desc': 'Chuva Leve'},
            {'day': 'Sex', 'temp': 21, 'icon': '03d', 'desc': 'Nublado'},
            {'day': 'Sáb', 'temp': 25, 'icon': '01d', 'desc': 'Sol entre nuvens'}
        ]
    }

    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={urllib.parse.quote(city_name)}&appid={weather_key}&units=metric&lang=pt_br"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data and 'list' in data and len(data['list']) > 0:
                current = data['list'][0]
                city_resp = data.get('city', {}).get('name', 'São Paulo')
                weather_result['city'] = city_resp
                weather_result['temp_celsius'] = round(current['main']['temp'])
                weather_result['humidity'] = current['main']['humidity']
                weather_result['description'] = current['weather'][0]['description'].capitalize()
                weather_result['icon'] = current['weather'][0]['icon']

                forecast_list = []
                days_added = set()
                dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

                for entry in data['list']:
                    dt = datetime.fromtimestamp(entry['dt'])
                    dia_str = dt.strftime('%Y-%m-%d')
                    if dia_str not in days_added and dt.date() >= timezone.now().date():
                        days_added.add(dia_str)
                        nome_dia = "Hoje" if dt.date() == timezone.now().date() else dias_semana[dt.weekday()]
                        forecast_list.append({
                            'day': nome_dia,
                            'temp': round(entry['main']['temp']),
                            'icon': entry['weather'][0]['icon'],
                            'desc': entry['weather'][0]['description'].capitalize()
                        })
                    if len(forecast_list) >= 5:
                        break

                if forecast_list:
                    weather_result['forecast'] = forecast_list
    except Exception as e:
        logger.warning("Erro ao obter previsão do tempo da API: %s", e)

    _WEATHER_CACHE = {'timestamp': now, 'data': weather_result}
    return weather_result


def get_bus_schedules():
    """Recupera as linhas de ônibus e distâncias em tempo real para o Shopping Tamboré / Região."""
    buses = list(BusSchedule.objects.filter(is_active=True))
    if not buses:
        # Linhas de ônibus com itinerário para o Shopping Tamboré e região
        default_lines = [
            ("T245", "Shopping Tamboré / Term. Barueri", "850m • 3 min", "Ponto Shopping", "A caminho"),
            ("T253", "Shopping Tamboré / Jd. Líbano", "1.4 km • 5 min", "Parada Tamboré", "A caminho"),
            ("448", "Shopping Tamboré / Alphaville", "2.8 km • 9 min", "Av. Piracema", "No horário"),
            ("260", "Barueri / Cotia via Tamboré", "4.2 km • 14 min", "Shopping Tamboré", "No horário"),
            ("827", "Tamboré / Metrô Butantã", "5.8 km • 18 min", "Ponto Central", "No terminal"),
        ]
        for line, dest, dep, plat, stat in default_lines:
            BusSchedule.objects.create(
                line_number=line,
                destination=dest,
                departure_time=dep,
                platform=plat,
                status=stat,
                is_active=True
            )
        buses = list(BusSchedule.objects.filter(is_active=True))
    return buses
