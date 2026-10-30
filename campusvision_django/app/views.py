import json
import logging
import os
import ast
import unicodedata
import re
import time
import shutil
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import connection
from django.utils import timezone

from .utils import (
    mod_counter, alert_status, add_message, add_slide, allowed_file, appr_slide,
    remove_slide, update_alert, get_slides, get_message, update_settings, get_settings,
    update_slide, get_video, update_feed_access, get_news_feed, get_weather_data,
    get_bus_schedules, signups_allowed, is_news_enabled_for_feed, trigger_feed_reload
)
from .models import Message, Slide, Room, FeedStatus, User, BusSchedule
from .forms import CustomUserCreationForm

logger = logging.getLogger(__name__)

_SCHEMA_CHECKED = False

def ensure_db_schema():
    """Garante de forma transparente que as colunas show_news e reload_id existam no banco legado."""
    global _SCHEMA_CHECKED
    if _SCHEMA_CHECKED:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM `FeedStatus` LIKE 'show_news';")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE `FeedStatus` ADD COLUMN `show_news` TINYINT(1) NOT NULL DEFAULT 1;")
            cursor.execute("SHOW COLUMNS FROM `FeedStatus` LIKE 'reload_id';")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE `FeedStatus` ADD COLUMN `reload_id` INT NOT NULL DEFAULT 0;")
        _SCHEMA_CHECKED = True
    except Exception:
        pass

def get_current_user_name(request):
    """Retorna o nome do usuário autenticado ou perfil padrão."""
    if request.user.is_authenticated:
        return getattr(request.user, 'name', None) or request.user.get_username()
    return "Visitante"

def signup_view(request):
    """Permite o cadastro de novos usuários com suporte a senha hasheada."""
    if not signups_allowed() and not (request.user.is_authenticated and getattr(request.user, 'is_admin', False)):
        messages.error(request, "Novos cadastros estão temporariamente desativados pelo administrador.")
        return redirect('login')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta criada com sucesso! Faça seu login.")
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'app/signup.html', {
        'form': form,
        'title': 'Novo Cadastro',
        'name': get_current_user_name(request),
        'mod_count': mod_counter()
    })

def login_view(request):
    """Autenticação de usuários."""
    if request.user.is_authenticated:
        return redirect('manager')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Bem-vindo(a), {getattr(user, 'name', user.email)}!")
            return redirect('manager')
        else:
            messages.error(request, "E-mail ou senha inválidos.")
    return render(request, 'app/login.html', {
        'title': 'Login'
    })

def logout_view(request):
    """Encerra a sessão do usuário."""
    logout(request)
    messages.info(request, "Você saiu da sua conta.")
    return redirect('login')

def index(request):
    """Página inicial com estatísticas e feeds disponíveis."""
    ensure_db_schema()
    settings_obj = get_settings()
    try:
        feeds_list = ast.literal_eval(settings_obj.feeds)
        if not isinstance(feeds_list, list):
            feeds_list = ['Default']
    except Exception:
        feeds_list = ['Default']

    feed_details = []
    status_map = {fs.feed_name: fs for fs in FeedStatus.objects.all()}
    
    for feed_name in feeds_list:
        fs = status_map.get(feed_name)
        is_online = bool(fs and fs.is_recently_updated == 1)
        last_seen = fs.last_access if fs else None
        show_news = bool(getattr(fs, 'show_news', True)) if fs else True
        slides_count = len(get_slides(feed_name, interleave_news=False))
        
        feed_details.append({
            'name': feed_name,
            'is_online': is_online,
            'last_access': last_seen,
            'show_news': show_news,
            'slides_count': slides_count,
            'url_horizontal': reverse('feeds', kwargs={'title': feed_name}),
            'url_vertical': reverse('feeds_vertical', kwargs={'title': feed_name}),
        })

    return render(request, 'app/home.html', {
        'title': 'Dashboard',
        'mod_count': mod_counter(),
        'feeds': feeds_list,
        'feed_details': feed_details,
        'total_tvs': len(feeds_list),
        'online_tvs': sum(1 for f in feed_details if f['is_online']),
        'clients': request.session.get('active_clients', []),
        'name': get_current_user_name(request)
    })

def manager(request):
    """Gerenciador de slides enviados."""
    page_number = request.GET.get('page', 1)
    posts = Slide.objects.all().order_by('-id')
    paginator = Paginator(posts, getattr(settings, 'POSTS_PER_PAGE', 10))
    page_obj = paginator.get_page(page_number)

    for slide in page_obj.object_list:
        if isinstance(slide.feeds, str):
            try:
                slide.feeds_list = [feed.strip("'\" ").strip() for feed in slide.feeds.strip('][').split(',') if feed.strip()]
            except Exception:
                slide.feeds_list = [slide.feeds]
        else:
            slide.feeds_list = []

    return render(request, 'app/manager.html', {
        'title': 'Todos os Slides',
        'users': page_obj.object_list,
        'name': get_current_user_name(request),
        'filter': ['Approved', 'Waiting Review', 'Denied'],
        'mod_count': mod_counter(),
        'next_url': f"{reverse('manager')}?page={page_obj.next_page_number()}" if page_obj.has_next() else None,
        'prev_url': f"{reverse('manager')}?page={page_obj.previous_page_number()}" if page_obj.has_previous() else None,
    })

def manager_approved(request):
    page_number = request.GET.get('page', 1)
    posts = Slide.objects.filter(approval='Approved').order_by('-id')
    paginator = Paginator(posts, settings.POSTS_PER_PAGE)
    page_obj = paginator.get_page(page_number)
    return render(request, 'app/manager.html', {
        'title': 'Slides Aprovados',
        'users': page_obj.object_list,
        'name': get_current_user_name(request),
        'filter': ['Approved'],
        'mod_count': mod_counter(),
        'next_url': f"{reverse('manager_approved')}?page={page_obj.next_page_number()}" if page_obj.has_next() else None,
        'prev_url': f"{reverse('manager_approved')}?page={page_obj.previous_page_number()}" if page_obj.has_previous() else None,
    })

def manager_waiting(request):
    page_number = request.GET.get('page', 1)
    posts = Slide.objects.filter(approval='Waiting Review').order_by('-id')
    paginator = Paginator(posts, settings.POSTS_PER_PAGE)
    page_obj = paginator.get_page(page_number)
    return render(request, 'app/manager.html', {
        'title': 'Slides Aguardando Revisão',
        'users': page_obj.object_list,
        'name': get_current_user_name(request),
        'filter': ['Waiting Review'],
        'mod_count': mod_counter(),
        'next_url': f"{reverse('manager_waiting')}?page={page_obj.next_page_number()}" if page_obj.has_next() else None,
        'prev_url': f"{reverse('manager_waiting')}?page={page_obj.previous_page_number()}" if page_obj.has_previous() else None,
    })

def manager_denied(request):
    page_number = request.GET.get('page', 1)
    posts = Slide.objects.filter(approval='Denied').order_by('-id')
    paginator = Paginator(posts, settings.POSTS_PER_PAGE)
    page_obj = paginator.get_page(page_number)
    return render(request, 'app/manager.html', {
        'title': 'Slides Reprovados',
        'users': page_obj.object_list,
        'name': get_current_user_name(request),
        'filter': ['Denied'],
        'mod_count': mod_counter(),
        'next_url': f"{reverse('manager_denied')}?page={page_obj.next_page_number()}" if page_obj.has_next() else None,
        'prev_url': f"{reverse('manager_denied')}?page={page_obj.previous_page_number()}" if page_obj.has_previous() else None,
    })

def profile(request):
    return render(request, 'app/profile.html', {
        'title': 'Perfil',
        'name': get_current_user_name(request),
        'mod_count': mod_counter()
    })

def upload_file(request):
    settings_obj = get_settings()
    try:
        feeds_list = ast.literal_eval(settings_obj.feeds)
    except Exception:
        feeds_list = ['Default']

    if request.method == 'GET':
        return render(request, 'app/upload.html', {
            'title': 'Upload de Slide',
            'name': get_current_user_name(request),
            'mod_count': mod_counter(),
            'feeds': feeds_list
        })
    elif request.method == 'POST':
        media_type = request.POST.get('media_type', 'image')
        embed_url = request.POST.get('embed_url', '').strip()
        time_start = request.POST.get("time_start", "")
        time_end = request.POST.get("time_end", "")
        title = request.POST.get("title", "").strip()
        feed_list = request.POST.getlist('feeds')
        reading_time = request.POST.get('reading_time', 15)
        submitted_by = get_current_user_name(request)

        # Se for um painel / link embed
        is_admin_user = request.user.is_authenticated and (getattr(request.user, 'is_admin', False) or getattr(request.user, 'is_staff', False))
        auto_approve = request.POST.get('auto_approve') == '1' or is_admin_user
        initial_approval = "Approved" if auto_approve else "Waiting Review"

        if media_type == 'embed' or (embed_url and embed_url.startswith(('http://', 'https://'))):
            if not embed_url.startswith(('http://', 'https://')):
                messages.error(request, 'URL do painel inválida. Insira uma URL completa iniciando com http:// ou https://')
                return redirect('upload')
            
            slide_path = embed_url
            if not title:
                title = "Painel Web"

            add_slide(time_start, time_end, title, slide_path, feed_list, submitted_by=submitted_by, reading_time=reading_time, approval=initial_approval)
            if initial_approval == "Approved":
                messages.success(request, f"Painel '{title}' publicado e ativado imediatamente nas TVs!")
            else:
                messages.success(request, f"Painel '{title}' adicionado com sucesso para moderação!")
            return redirect('manager')

        # Se for upload de arquivo físico (Imagem ou Vídeo)
        file = request.FILES.get('file')
        if not file or not file.name:
            messages.error(request, 'Nenhum arquivo ou URL selecionado.')
            return redirect('upload')

        if allowed_file(file.name):
            raw_title = title or file.name

            # Sanitiza o nome do arquivo para compatibilidade universal em Linux/Nginx/Web
            base_name, ext = os.path.splitext(file.name)
            clean_base = unicodedata.normalize('NFKD', base_name).encode('ASCII', 'ignore').decode('ASCII')
            clean_base = re.sub(r'[^\w\s-]', '', clean_base).strip().replace(' ', '_')
            clean_base = re.sub(r'[-_]+', '_', clean_base)
            if not clean_base:
                clean_base = f"media_{int(time.time())}"
            final_filename = f"{clean_base}_{int(time.time())}{ext.lower()}"

            # Grava o arquivo simultaneamente em app/static/uploads, staticfiles/uploads e media
            target_dirs = [
                os.path.join(settings.BASE_DIR, 'app', 'static', 'uploads'),
                os.path.join(settings.BASE_DIR, 'staticfiles', 'uploads'),
                os.path.join(settings.BASE_DIR, 'media'),
            ]

            saved_path = None
            for target_dir in target_dirs:
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    dest_file = os.path.join(target_dir, final_filename)
                    if saved_path and os.path.exists(saved_path):
                        if not os.path.exists(dest_file) or not os.path.samefile(saved_path, dest_file):
                            shutil.copy2(saved_path, dest_file)
                    else:
                        with open(dest_file, 'wb+') as destination:
                            for chunk in file.chunks():
                                destination.write(chunk)
                        saved_path = dest_file
                except Exception as e:
                    logger.warning(f"Erro ao salvar arquivo em {target_dir}: {e}")

            if not title:
                title = raw_title
            slide_path = final_filename

            add_slide(time_start, time_end, title, slide_path, feed_list, submitted_by=submitted_by, reading_time=reading_time, approval=initial_approval)
            if initial_approval == "Approved":
                messages.success(request, f"Slide '{title}' publicado e ativado imediatamente nas TVs!")
            else:
                messages.success(request, f"Slide '{title}' enviado com sucesso para moderação!")
            return redirect('manager')
        else:
            messages.error(request, 'Tipo de arquivo não permitido. Envie apenas imagens (.jpg, .png, .webp) ou vídeos (.mp4, .webm).')
            return redirect('upload')

def moderate(request):
    """Painel de moderação de slides para administradores."""
    page_number = request.GET.get('page', 1)
    posts = Slide.objects.all().order_by('-id')
    paginator = Paginator(posts, getattr(settings, 'POSTS_PER_PAGE', 10))
    page_obj = paginator.get_page(page_number)

    for slide in page_obj.object_list:
        if isinstance(slide.feeds, str):
            try:
                slide.feeds_list = [feed.strip("'\" ").strip() for feed in slide.feeds.strip('][').split(',') if feed.strip()]
            except Exception:
                slide.feeds_list = [slide.feeds]
        else:
            slide.feeds_list = []

    return render(request, 'app/moderate.html', {
        'title': 'Moderação de Slides',
        'name': get_current_user_name(request),
        'users': page_obj.object_list,
        'filter': ['Approved', 'Waiting Review', 'Denied'],
        'mod_count': mod_counter(),
        'next_url': f"{reverse('mod')}?page={page_obj.next_page_number()}" if page_obj.has_next() else None,
        'prev_url': f"{reverse('mod')}?page={page_obj.previous_page_number()}" if page_obj.has_previous() else None,
    })

def moderate_post(request):
    if request.method == 'POST':
        slide_id = request.POST.get('slide_id')
        slide = Slide.objects.filter(id=slide_id).first()
        slide_feeds = slide.feeds if slide else None
        if 'Approve' in request.POST:
            appr_slide('Approved', slide_id)
            trigger_feed_reload(slide_feeds)
            messages.success(request, "Slide aprovado com sucesso e publicado nas TVs!")
        elif 'Deny' in request.POST:
            appr_slide('Denied', slide_id)
            trigger_feed_reload(slide_feeds)
            messages.warning(request, "Slide reprovado.")
        elif 'Delete' in request.POST:
            remove_slide(slide_id)
            trigger_feed_reload(slide_feeds)
            messages.info(request, "Slide excluído.")
    return redirect('mod')

def edit(request, id):
    slide = get_object_or_404(Slide, pk=id)
    settings_obj = get_settings()
    try:
        feeds_list = ast.literal_eval(settings_obj.feeds)
    except Exception:
        feeds_list = ['Default']

    if request.method == 'GET':
        return render(request, 'app/edit.html', {
            'title': 'Editar Slide',
            'slide_id': id,
            'slide': slide,
            'name': get_current_user_name(request),
            'mod_count': mod_counter(),
            'feeds': feeds_list
        })
    elif request.method == 'POST':
        title = request.POST.get("title_text", slide.title)
        time_start = request.POST.get("time_start", slide.time_start)
        time_end = request.POST.get("time_end", slide.time_end)
        selected_feeds = request.POST.getlist('feeds')
        reading_time = request.POST.get('reading_time', slide.reading_time or 10)

        update_slide(id, title, time_start, time_end, selected_feeds, reading_time=reading_time)
        trigger_feed_reload(selected_feeds)
        messages.success(request, "Slide atualizado com sucesso e transmitido para as TVs!")
        return redirect('manager')

def messages_view(request):
    if request.method == 'POST':
        text = request.POST.get("message_text", "").strip()
        start_time = request.POST.get("time_start", "")
        end_time = request.POST.get("time_end", "")
        if text:
            add_message(text, start_time, end_time, submitted_by=get_current_user_name(request))
            messages.success(request, "Mensagem publicada com sucesso!")
        return redirect('messages')

    return render(request, 'app/messages.html', {
        'title': 'Mensagens do Painel',
        'name': get_current_user_name(request),
        'mod_count': mod_counter(),
        'messages': Message.objects.all().order_by('-id')
    })

def alerts(request):
    if request.method == 'POST':
        status_action = request.POST.get("alert_status")
        if status_action == "Enable":
            text = request.POST.get("alert_text", "").strip()
            update_alert(text)
            messages.warning(request, "Alerta de emergência ativado!")
        elif status_action == "Disable":
            update_alert("")
            messages.success(request, "Alerta desativado.")
        return redirect('alerts')

    return render(request, 'app/alerts.html', {
        'title': 'Alerta de Emergência',
        'name': get_current_user_name(request),
        'mod_count': mod_counter(),
        'alert_text': alert_status()
    })

def settings_view(request):
    if request.method == 'POST':
        duration_time = request.POST.get("duration", "10000")
        allow_signups = request.POST.get("allow_signups", 1)
        feed_list = request.POST.get("feeds", "['Default']")
        update_settings(duration_time, allow_signups, feed_list)
        messages.success(request, "Configurações salvas com sucesso!")
        return redirect('settings')

    return render(request, 'app/settings.html', {
        'title': 'Configurações do Sistema',
        'name': get_current_user_name(request),
        'mod_count': mod_counter(),
        'settings': get_settings()
    })

def feeds(request, title):
    """Exibição principal da TV com Slides, Notícias, Clima e Ônibus."""
    ensure_db_schema()
    update_feed_access(title)
    settings_obj = get_settings()
    weather_data = get_weather_data()
    bus_lines = get_bus_schedules()
    slides_data = get_slides(title)
    messages_data = get_message()
    fs = FeedStatus.objects.filter(feed_name=title).first()
    reload_id = getattr(fs, 'reload_id', 0) if fs else 0

    return render(request, 'app/feed.html', {
        'title': title,
        'slides': slides_data,
        'alert_status': alert_status(),
        'interval': settings_obj.duration or "10000",
        'messages': messages_data,
        'weather': weather_data,
        'buses': bus_lines,
        'reload_id': reload_id,
        'background': f"{title}.webp",
        'weather_key': settings.WEATHER_KEY
    })

def feeds_vertical(request, title):
    """Exibição para telas verticais (Totens)."""
    ensure_db_schema()
    update_feed_access(title)
    settings_obj = get_settings()
    fs = FeedStatus.objects.filter(feed_name=title).first()
    reload_id = getattr(fs, 'reload_id', 0) if fs else 0

    return render(request, 'app/feed_vertical.html', {
        'title': title,
        'slides': get_slides(title),
        'alert_status': alert_status(),
        'interval': settings_obj.duration or "10000",
        'messages': get_message(),
        'weather': get_weather_data(),
        'buses': get_bus_schedules(),
        'reload_id': reload_id,
        'background': 'background-square.png',
        'weather_key': settings.WEATHER_KEY
    })

def feeds_video(request, title):
    ensure_db_schema()
    update_feed_access(title)
    return render(request, 'app/feed-video.html', {
        'title': title,
        'video': get_video(title),
        'alert_status': alert_status(),
        'interval': get_settings().duration,
        'messages': json.dumps(get_message()),
        'background': f"{title}.webp",
        'weather_key': settings.WEATHER_KEY
    })

def status(request):
    ensure_db_schema()
    return render(request, 'app/status.html', {
        'title': 'Status Operacional das Telas',
        'rooms': FeedStatus.objects.all(),
        'name': get_current_user_name(request),
        'mod_count': mod_counter()
    })

def configuration_equipment(request):
    """Gerenciamento e configuração de equipamentos e salas, incluindo flag de notícias."""
    ensure_db_schema()
    settings_obj = get_settings()
    try:
        feeds_list = ast.literal_eval(settings_obj.feeds)
        if not isinstance(feeds_list, list):
            feeds_list = []
    except Exception:
        feeds_list = []

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            feed_name = request.POST.get('feed_name', '').strip()
            show_news = request.POST.get('show_news') == '1'
            if feed_name:
                fs, created = FeedStatus.objects.get_or_create(
                    feed_name=feed_name,
                    defaults={'last_access': timezone.now(), 'is_recently_updated': 1, 'show_news': show_news}
                )
                if not created:
                    fs.show_news = show_news
                    fs.save()

                if feed_name not in feeds_list:
                    feeds_list.append(feed_name)
                    settings_obj.feeds = str(feeds_list)
                    settings_obj.save()

                Room.objects.get_or_create(id=feed_name, defaults={'title': f"Equipamento {feed_name}", 'status': 1})
                status_news = "Ativadas" if show_news else "Desativadas"
                messages.success(request, f"Equipamento '{feed_name}' salvo com sucesso! Notícias: {status_news}.")
        elif action == 'toggle_news':
            feed_name = request.POST.get('feed_name')
            fs = FeedStatus.objects.filter(feed_name=feed_name).first()
            if fs:
                fs.show_news = not fs.show_news
                fs.save()
                status_str = "ativadas" if fs.show_news else "desativadas"
                messages.success(request, f"Notícias {status_str} para o equipamento {feed_name}.")
            else:
                FeedStatus.objects.create(
                    feed_name=feed_name,
                    last_access=timezone.now(),
                    is_recently_updated=1,
                    show_news=False
                )
                messages.success(request, f"Notícias desativadas para o equipamento {feed_name}.")
            trigger_feed_reload(feed_name)
        elif action == 'reload':
            feed_name = request.POST.get('feed_name')
            if feed_name == '__ALL__':
                trigger_feed_reload('__ALL__')
                messages.success(request, "🔄 Comando de recarregamento remoto enviado para TODAS as TVs! Elas atualizarão em instantes.")
            else:
                trigger_feed_reload(feed_name)
                messages.success(request, f"🔄 Comando de recarregamento remoto enviado para a TV '{feed_name}'. Ela atualizará em instantes!")
        elif action == 'delete':
            feed_name = request.POST.get('feed_name')
            if feed_name in feeds_list:
                feeds_list.remove(feed_name)
                settings_obj.feeds = str(feeds_list)
                settings_obj.save()
            FeedStatus.objects.filter(feed_name=feed_name).delete()
            Room.objects.filter(id=feed_name).delete()
            messages.info(request, f"Equipamento {feed_name} removido.")

        return redirect('configuration_equipment')

    status_map = {fs.feed_name: fs for fs in FeedStatus.objects.all()}
    all_equipments = []
    
    # Combina feeds de Settings com registros em FeedStatus
    all_names = list(dict.fromkeys(feeds_list + [fs.feed_name for fs in FeedStatus.objects.all()]))
    for name in all_names:
        fs = status_map.get(name)
        all_equipments.append({
            'feed_name': name,
            'is_online': bool(fs and fs.is_recently_updated == 1),
            'last_access': fs.last_access if fs else None,
            'show_news': bool(getattr(fs, 'show_news', True)) if fs else True,
            'slides_count': len(get_slides(name, interleave_news=False)),
            'url_horizontal': reverse('feeds', kwargs={'title': name}),
            'url_vertical': reverse('feeds_vertical', kwargs={'title': name}),
        })

    return render(request, 'app/configuration_equipment.html', {
        'title': 'Equipamentos e Salas',
        'rooms': all_equipments,
        'name': get_current_user_name(request),
        'mod_count': mod_counter()
    })

def usermanager(request):
    """Gerenciador de usuários do sistema."""
    return render(request, 'app/manager-users.html', {
        'title': 'Gerenciamento de Usuários',
        'users': User.objects.all(),
        'name': get_current_user_name(request),
        'mod_count': mod_counter()
    })

def bus_manager(request):
    """Permite adicionar, editar ou remover linhas de ônibus exibidas na TV."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            line_number = request.POST.get('line_number', '').strip()
            destination = request.POST.get('destination', '').strip()
            departure_time = request.POST.get('departure_time', '').strip()
            platform = request.POST.get('platform', 'Ponto Principal').strip()
            status_text = request.POST.get('status', 'No horário').strip()
            if line_number and destination:
                BusSchedule.objects.create(
                    line_number=line_number,
                    destination=destination,
                    departure_time=departure_time,
                    platform=platform,
                    status=status_text,
                    is_active=True
                )
                messages.success(request, f"Linha {line_number} cadastrada com sucesso!")
        elif action == 'delete':
            bus_id = request.POST.get('bus_id')
            BusSchedule.objects.filter(id=bus_id).delete()
            messages.info(request, "Linha de ônibus removida.")
        elif action == 'toggle':
            bus_id = request.POST.get('bus_id')
            bus_item = BusSchedule.objects.filter(id=bus_id).first()
            if bus_item:
                bus_item.is_active = not bus_item.is_active
                bus_item.save()
        return redirect('bus_manager')

    return render(request, 'app/bus_manager.html', {
        'title': 'Linhas de Ônibus & Transporte',
        'buses': BusSchedule.objects.all(),
        'name': get_current_user_name(request),
        'mod_count': mod_counter()
    })

def api_feed_data(request, feed_name):
    """Retorna todos os dados da TV em JSON para atualização em tempo real."""
    ensure_db_schema()
    update_feed_access(feed_name)
    slides = get_slides(feed_name)
    weather = get_weather_data()
    news = get_news_feed(limit=8)
    buses = [
        {
            'line': b.line_number,
            'dest': b.destination,
            'time': b.departure_time,
            'platform': b.platform,
            'status': b.status
        }
        for b in get_bus_schedules()
    ]
    fs = FeedStatus.objects.filter(feed_name=feed_name).first()
    reload_id = getattr(fs, 'reload_id', 0) if fs else 0

    response = JsonResponse({
        'slides': slides,
        'alert': alert_status(),
        'weather': weather,
        'news': news,
        'buses': buses,
        'messages': get_message(),
        'reload_id': reload_id,
        'show_news': getattr(fs, 'show_news', True) if fs else True,
    })
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
