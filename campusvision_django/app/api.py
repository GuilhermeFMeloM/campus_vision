from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from .models import Slide, Message
from .utils import parse_date_safe, get_news_feed, get_weather_data, get_bus_schedules, feed_matches
import logging

logger = logging.getLogger(__name__)

@require_GET
def slides(request, feed):
    slide_set = []
    today_date = timezone.now().date()
    for slide in Slide.objects.all().order_by('-id'):
        start_date = parse_date_safe(slide.time_start)
        end_date = parse_date_safe(slide.time_end)

        is_valid_date = True
        if start_date and today_date < start_date:
            is_valid_date = False
        if end_date and today_date > end_date:
            is_valid_date = False

        if feed_matches(feed, slide.feeds) and slide.approval == 'Approved' and is_valid_date:
            slide_set.append({
                'title': slide.title,
                'url': f'/static/uploads/{slide.slide_path}',
                'reading_time': slide.reading_time or 10
            })
    return JsonResponse(slide_set, safe=False)

@require_GET
def messages(request):
    message_set = []
    today_date = timezone.now().date()
    for item in Message.objects.all().order_by('-id'):
        start_date = parse_date_safe(item.time_start)
        end_date = parse_date_safe(item.time_end)

        is_valid = True
        if start_date and today_date < start_date:
            is_valid = False
        if end_date and today_date > end_date:
            is_valid = False

        if is_valid and item.text and item.text.strip():
            message_set.append(item.text.strip())
    return JsonResponse(message_set, safe=False)
