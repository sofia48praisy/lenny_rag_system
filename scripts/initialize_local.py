"""Create a localhost-only PostgreSQL cluster for this workspace without Docker."""
import argparse
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, default=Path('D:/lenny-runtime'))
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    postgres = runtime / 'postgres-community' / 'pgsql'
    pg_bin = postgres / 'bin'
    data = runtime / 'pgdata'
    local = PROJECT / '.local'
    local.mkdir(exist_ok=True)
    password_file = local / 'database-password.txt'
    config_file = local / 'runtime.json'
    if not password_file.exists():
        password_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
    password = password_file.read_text(encoding='utf-8').strip()
    env = {**os.environ, 'PGPASSWORD': password}

    def run(name, *arguments, check=True):
        return subprocess.run([str(pg_bin / f'{name}.exe'), *map(str, arguments)],
                              env=env, check=check, creationflags=subprocess.CREATE_NO_WINDOW)

    for folder in ['lib', 'share/extension']:
        for source in (runtime / 'pgvector-msvc' / folder).glob('*'):
            if source.is_file():
                target = postgres / folder / source.name
                if not target.exists() or target.read_bytes() != source.read_bytes():
                    shutil.copy2(source, target)
    if not (data / 'PG_VERSION').exists():
        run('initdb', '-D', data, '-U', 'lenny', '--pwfile', password_file,
            '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C')
        with (data / 'postgresql.conf').open('a', encoding='utf-8') as f:
            f.write("\n# Local Lenny runtime\nlisten_addresses = '127.0.0.1'\nport = 5433\nshared_buffers = '128MB'\nmax_connections = 30\n")
    if run('pg_ctl', '-D', data, 'status', check=False).returncode != 0:
        run('pg_ctl', '-D', data, '-l', runtime / 'postgres.log', '-w', 'start')
    exists = subprocess.check_output([str(pg_bin / 'psql.exe'), '-h', '127.0.0.1', '-p', '5433',
                                      '-U', 'lenny', '-d', 'postgres', '-tAc',
                                      "SELECT 1 FROM pg_database WHERE datname='lenny'"], env=env, text=True).strip()
    if exists != '1':
        run('createdb', '-h', '127.0.0.1', '-p', '5433', '-U', 'lenny', 'lenny')
    url = f'postgresql+asyncpg://lenny:{password}@127.0.0.1:5433/lenny'
    configuration = {'database_url': url, 'runtime': str(runtime), 'postgres_bin': str(pg_bin)}
    config_file.write_text(json.dumps(configuration, indent=2), encoding='utf-8')
    env_file = PROJECT / 'backend' / '.env'
    if env_file.exists():
        print('Existing backend/.env preserved; use .local/runtime.json for the local DB URL.')
    else:
        env_file.write_text(f'DATABASE_URL={url}\nOLLAMA_BASE_URL=http://127.0.0.1:11434\nOLLAMA_MODEL=llama3.2:3b\nOLLAMA_CONTEXT=8192\nMODEL_TIMEOUT=600\n', encoding='utf-8')
    print('PostgreSQL is running on 127.0.0.1:5433. Local credentials are saved only in ignored files.')


if __name__ == '__main__':
    main()
