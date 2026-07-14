import os
import io
import tempfile

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections


SOURCE_DB = 'sqlite_legacy'


class Command(BaseCommand):
    help = 'Migra os dados do db.sqlite3 (alias sqlite_legacy) para o banco default (Postgres/Neon).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default=SOURCE_DB,
            help='Alias do banco de origem (default: sqlite_legacy).',
        )
        parser.add_argument(
            '--destination',
            default=DEFAULT_DB_ALIAS,
            help='Alias do banco de destino (default: default).',
        )
        parser.add_argument(
            '--exclude',
            action='append',
            default=[
                'contenttypes',
                'auth.permission',
                'sessions.session',
                'admin.logentry',
                'ai.chatmessage',
            ],
            help='App.Model(s) a ignorar (pode repetir).',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Apaga todos os registros do destino antes de copiar.',
        )

    def handle(self, *args, **options):
        source = options['source']
        destination = options['destination']
        excludes = options['exclude']
        reset = options['reset']

        if source not in settings.DATABASES:
            raise CommandError(
                f"Banco de origem '{source}' nao configurado. "
                "Verifique se db.sqlite3 existe na raiz do projeto."
            )
        if destination not in settings.DATABASES:
            raise CommandError(f"Banco de destino '{destination}' nao configurado.")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Migrando dados: {source} -> {destination}"
        ))

        # Valida tabelas na origem
        try:
            connections[source].ensure_connection()
        except Exception as exc:
            raise CommandError(f"Nao foi possivel conectar ao banco '{source}': {exc}")

        if reset:
            self._reset_destination(destination, excludes)

        excludes = list(excludes)
        excludes.extend(self._missing_tables_exclusions(source))
        excludes = list(dict.fromkeys(excludes))  # dedup preservando ordem

        with tempfile.NamedTemporaryFile(
            mode='w+', suffix='.json', delete=False, encoding='utf-8'
        ) as tmp:
            tmp_path = tmp.name

        try:
            self.stdout.write("Gerando dump do banco de origem...")
            buffer = io.StringIO()
            call_command(
                'dumpdata',
                format='json',
                database=source,
                natural_foreign=True,
                natural_primary=True,
                indent=2,
                exclude=excludes,
                stdout=buffer,
            )
            dump_text = buffer.getvalue()

            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(dump_text)

            self.stdout.write("Carregando dump no banco de destino...")
            call_command(
                'loaddata',
                tmp_path,
                database=destination,
                ignorenonexistent=True,
                verbosity=1,
            )

            os.unlink(tmp_path)
            self.stdout.write(self.style.SUCCESS(
                "Migracao SQLite -> Postgres concluida com sucesso!"
            ))
        except Exception as exc:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise CommandError(f"Falha na migracao: {exc}")

    def _missing_tables_exclusions(self, source):
        """Exclui models cujas tabelas ainda nao existem no banco de origem."""
        conn = connections[source]
        try:
            table_names = set(conn.introspection.table_names())
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Nao foi possivel introspectar {source}: {exc}"
            ))
            return []
        skip = []
        for model in apps.get_models():
            if model._meta.db_table not in table_names:
                skip.append(f"{model._meta.app_label}.{model._meta.model_name}")
        if skip:
            self.stdout.write(self.style.WARNING(
                "Tabelas ausentes no banco de origem (serao ignoradas): " + ", ".join(skip)
            ))
        return skip

    def _reset_destination(self, destination, excludes):
        self.stdout.write(self.style.WARNING(
            "--reset: limpando registros do banco de destino..."
        ))
        models_to_clear = [
            model
            for model in apps.get_models()
            if f"{model._meta.app_label}.{model._meta.model_name}" not in excludes
        ]
        for model in models_to_clear:
            qs = model.objects.using(destination).all()
            count = qs.count()
            if count:
                qs.delete()
                self.stdout.write(f"  - {model._meta.label}: {count} apagados")
