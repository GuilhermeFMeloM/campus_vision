from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.backends import BaseBackend

class User(models.Model):
    """Define o modelo de usuário do sistema."""
    email = models.EmailField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    name = models.CharField(max_length=1000)
    is_admin = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'User'
        managed =True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_staff(self):
        return self.is_admin

    @property
    def is_active(self):
        return True

    def get_username(self):
        return self.email

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password or not raw_password:
            return False
        # Checagem padrão do Django
        try:
            if check_password(raw_password, self.password):
                return True
        except Exception:
            pass

        # Checagem legado (Werkzeug / Plaintext)
        try:
            from werkzeug.security import check_password_hash
            if check_password_hash(self.password, raw_password):
                self.set_password(raw_password)
                self.save(update_fields=['password'])
                return True
        except Exception:
            pass

        if self.password == raw_password:
            self.set_password(raw_password)
            self.save(update_fields=['password'])
            return True

        return False

    def get_session_auth_hash(self):
        return self.password

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin

    def __str__(self):
        return self.name or self.email


class EmailAuthBackend(BaseBackend):
    """Backend de autenticação via e-mail e senha."""
    def authenticate(self, request, email=None, password=None, **kwargs):
        if not email or not password:
            return None
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class Slide(models.Model):
    """Define o modelo de slide"""
    slide_path = models.CharField(max_length=1000)
    time_start = models.CharField(max_length=1000)
    time_end = models.CharField(max_length=1000)
    title = models.CharField(max_length=1000)
    approval = models.CharField(max_length=1000, default='Waiting Review')
    submitted_by = models.CharField(max_length=1000)
    feeds = models.CharField(max_length=1000)
    reading_time = models.IntegerField(default=10)  # Tempo de exibição em segundos

    class Meta:
        db_table = 'Slide'
        managed =True

    def __str__(self):
        return self.title


class Alert(models.Model):
    """Define o modelo de alerta urgente"""
    alert_text = models.CharField(max_length=1000, null=True, blank=True)

    class Meta:
        db_table = 'Alert'
        managed =True

    def __str__(self):
        return f"Alert: {self.alert_text}"


class Message(models.Model):
    """Define o modelo de mensagem institucional/informativa"""
    time_start = models.CharField(max_length=1000)
    time_end = models.CharField(max_length=1000)
    text = models.CharField(max_length=1000)
    submitted_by = models.CharField(max_length=1000, default="Admin")

    class Meta:
        db_table = 'Message'
        managed =True

    def __str__(self):
        return self.text


class Settings(models.Model):
    """Define o modelo de configurações globais"""
    duration = models.CharField(max_length=1000, default="10000")
    allow_signups = models.IntegerField(default=1)
    feeds = models.CharField(max_length=1000, default="['Default']")

    class Meta:
        db_table = 'Settings'
        managed =True

    def __str__(self):
        return f"Settings {self.id}"


class Room(models.Model):
    """Define o modelo de sala / equipamento"""
    id = models.CharField(max_length=1000, primary_key=True)
    title = models.CharField(max_length=1000)
    status = models.IntegerField(default=1)

    class Meta:
        db_table = 'Room'
        managed =True

    def __str__(self):
        return self.title


class FeedStatus(models.Model):
    """Define o estado do feed e heartbeat da TV"""
    feed_name = models.CharField(max_length=255, primary_key=True)
    last_access = models.DateTimeField(default=timezone.now)
    is_recently_updated = models.IntegerField(default=0)
    show_news = models.BooleanField(default=True, help_text="Exibir notícias dinâmicas intercaladas neste equipamento")
    reload_id = models.IntegerField(default=0, help_text="Contador para forçar recarregamento remoto da TV")

    class Meta:
        db_table = 'FeedStatus'
        managed =True

    def __str__(self):
        return self.feed_name


class BusSchedule(models.Model):
    """Horários e distâncias de linhas de ônibus para o painel da TV"""
    line_number = models.CharField(max_length=50, help_text="Ex: 809U-10, Circular 1")
    destination = models.CharField(max_length=255, help_text="Ex: Metrô Butantã / Terminal Pinheiros")
    departure_time = models.CharField(max_length=100, help_text="Ex: 5 min, 12 min, 18:45")
    platform = models.CharField(max_length=100, blank=True, null=True, default="Ponto Principal")
    status = models.CharField(max_length=50, default="No horário")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'BusSchedule'
        managed =True
        ordering = ['id']

    def __str__(self):
        return f"{self.line_number} -> {self.destination} ({self.departure_time})"
