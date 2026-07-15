import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

ENVIRONMENT = os.getenv('DJANGO_ENV', 'dev')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'unsafe-default-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'widget_tweaks',
    'django_celery_beat',
    'django_celery_results',

    'tenants',
    'authentication',
    'waha',
    'brands',
    'categories',
    'suppliers',
    'products',
    'inflows',
    'outflows',
    'ai',
    'app',
]

LOGIN_URL = 'login'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'app.middleware.TenantMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['app/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app.context_processors.user_theme',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
#
# Prioridade de configuracao do banco:
#   1. POSTGRES_URL (NeonDB / qualquer Postgres de producao)
#   2. Container local ``sge_db`` quando DJANGO_ENV == 'prd'
#   3. SQLite local (dev)


def _build_postgres_config(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    options = {}
    for opt_key in ('sslmode', 'channel_binding'):
        if opt_key in query:
            options[opt_key] = query[opt_key][0]
    return {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': parsed.path.lstrip('/'),
        'USER': parsed.username or 'postgres',
        'PASSWORD': parsed.password or '',
        'HOST': parsed.hostname or 'localhost',
        'PORT': str(parsed.port or 5432),
        'OPTIONS': options or {},
    }


POSTGRES_URL = os.getenv('POSTGRES_URL', '').strip()

if POSTGRES_URL:
    DATABASES = {'default': _build_postgres_config(POSTGRES_URL)}
elif ENVIRONMENT == 'prd':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': os.getenv('POSTGRES_DB', 'sge'),
            'USER': os.getenv('POSTGRES_USER', 'caio'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'caiopass'),
            'HOST': os.getenv('POSTGRES_HOST', 'sge_db'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Alias para o SQLite legado, usado pelo comando de migracao SQLite -> Postgres
SQLITE_LEGACY_PATH = BASE_DIR / 'db.sqlite3'
if DATABASES['default'].get('ENGINE') != 'django.db.backends.sqlite3' and SQLITE_LEGACY_PATH.exists():
    DATABASES['sqlite_legacy'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': SQLITE_LEGACY_PATH,
        'TEST': {'NAME': None},
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'pt-BR'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
        'rest_framework.permissions.DjangoModelPermissions',
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'pyamqp://guest:guest@localhost:5672//')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'django-db')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TIMEZONE = 'America/Sao_Paulo'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# WAHA
WAHA_BASE_URL = os.getenv('WAHA_BASE_URL', 'http://localhost:3000' if ENVIRONMENT == 'dev' else 'http://waha:3000')
WAHA_WEBHOOK_URL = os.getenv('WAHA_WEBHOOK_URL', '')
WAHA_API_KEY = os.getenv('WAHA_API_KEY', '')

# Email
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('SMTP_HOST', '')
EMAIL_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_HOST_USER = os.getenv('SMTP_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('SMTP_FROM', '')

# Upload
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50 MB
