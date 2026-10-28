"""
Django settings for campusvision_django project.
"""

from pathlib import Path
import os
import dj_database_url  # <-- ADICIONE ESTA LINHA AQUI
import pymysql
pymysql.install_as_MySQLdb()


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-9sn0pp=#st+3b6x==%d#k)32cb@e2fm5qq$ft_4^dmztn&v-_1')

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
DEBUG = True

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# CSRF Trusted Origins para Google Cloud Run e domínios personalizados
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'https://*.run.app,http://127.0.0.1:8000,http://localhost:8000'
    ).split(',') if origin.strip()
]

# Permitir incorporação de iframes (Dashboards/Embeds)
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Adiciona WhiteNoise para servir arquivos estáticos em produção se disponível
try:
    import whitenoise
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
except ImportError:
    pass

AUTHENTICATION_BACKENDS = [
    'app.models.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'campusvision_django.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'app' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',
            ],
        },
    },
]

WSGI_APPLICATION = 'campusvision_django.wsgi.application'

# Database: Suporta Cloud SQL (Postgres / MySQL) via DATABASE_URL ou SQLite local/volume

 	
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'campusvision',
        'USER': '2BDbWRGd19pMRok.root',
        'PASSWORD': 'L9GNXy4wztJ5n9GS',
        'HOST': 'gateway01.us-east-1.prod.aws.tidbcloud.com',
        'PORT': '4000',
        'OPTIONS': {
            'ssl': {
                'ca': '/etc/ssl/certs/ca-certificates.crt' if os.path.exists('/etc/ssl/certs/ca-certificates.crt') else None,
                'check_hostname': False,
            }
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 4,
        }
    },
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images) com WhiteNoise
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'app' / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media uploads (Pode ser apontado para bucket montado via Cloud Run Volume)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'app' / 'static' / 'uploads'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

POSTS_PER_PAGE = 10
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'mp4', 'webp'}
WEATHER_KEY = os.environ.get('WEATHER_KEY', '99ec4e7d956393e48a8cda51317329c5')
WEATHER_CITY = os.environ.get('WEATHER_CITY', 'São Paulo,BR')
DEFAULT_DURATION = 10000
