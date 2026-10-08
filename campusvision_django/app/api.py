from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Slide, Message
from .utils import parse_date_safe, get_news_feed, get_weather_data, get_bus_schedules
import datetime
import logging

logger = logging.getLogger(__name__)

@require_GET
def slides(request, feed):
    slide_set = []
    today_date = datetime.date.today()
    for slide in Slide.objects.all().order_by('-id'):
        start_date = parse_date_safe(slide.time_start)
        end_date = parse_date_safe(slide.time_end)
        if start_date and end_date and not (start_date <= today_date <= end_date):
            continue
        if feed in slide.feeds and slide.approval == 'Approved':
            slide_set.append({
                'title': slide.title,
                'url': f'/static/uploads/{slide.slide_path}',
                'reading_time': slide.reading_time or 10
            })
    return JsonResponse(slide_set, safe=False)

@require_GET
def messages(request):
    message_set = []
    today_date = datetime.date.today()
    for item in Message.objects.all():
        start_date = parse_date_safe(item.time_start)
        end_date = parse_date_safe(item.time_end)
        if start_date and end_date and not (start_date <= today_date <= end_date):
            continue
        message_set.append(item.text)
    return JsonResponse(message_set, safe=False)