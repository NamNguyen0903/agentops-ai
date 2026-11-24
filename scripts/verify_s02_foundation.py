"""Verify local Compose in a new isolated project; retain its stopped resources.

No published ports, shared-stack mutations, auth activation or migrations.
Requires Docker Compose v2 with --wait. Uses generated test-only credentials.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import uuid

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    project = 'agentops-s02-foundation-' + uuid.uuid4().hex[:10]
    env = os.environ.copy()
    env.update(POSTGRES_BOOTSTRAP_PASSWORD=secrets.token_hex(32), POSTGRES_APP_PASSWORD=secrets.token_hex(32))
    redactions = [env['POSTGRES_BOOTSTRAP_PASSWORD'], env['POSTGRES_APP_PASSWORD']]

    def call(args, *, data=None, limit=300):
        result = subprocess.run(args, input=data, text=True, capture_output=True, env=env, cwd=root, timeout=limit)
        if result.returncode:
            diagnostic = (result.stdout + result.stderr)[-4000:]
            for secret in redactions:
                diagnostic = diagnostic.replace(secret, '[REDACTED]')
            print(diagnostic)
            raise RuntimeError(f'Command failed with exit {result.returncode}: {args[:3]}')
        return result.stdout

    assert not call(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project]).strip()
    assert not call(['docker', 'volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + project]).strip()
    rendered = json.loads(call(['docker', 'compose', '-p', project, '-f', str(root / 'compose.yaml'), 'config', '--format', 'json']))
    for service in rendered['services'].values():
        service.pop('ports', None)
    # Compose's normalized volume name can include a project prefix: force this new project.
    for key, volume in rendered['volumes'].items():
        volume['name'] = project + '_' + key
    print('ISOLATED PROJECT:', project, flush=True)
    with tempfile.TemporaryDirectory(prefix='s02-foundation-config-') as directory:
        config = Path(directory) / 'compose.json'
        config.write_text(json.dumps(rendered))
        config.chmod(0o600)
        base = ['docker', 'compose', '-p', project, '-f', str(config)]
        try:
            call(base + ['config', '--quiet'])
            print('PASS: configuration validation; no host ports', flush=True)
            call(base + ['up', '--build', '--wait', '--wait-timeout', '120', '-d'], limit=600)
            print('PASS: API, web and database healthchecks', flush=True)
            probe = '''import json, urllib.request
    expected = {"status":"ok", "service":"agentops-api"}
    for url in ("http://127.0.0.1:8000/api/v1/health", "http://web:5173/api/v1/health"):
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Host": "localhost:5173"} if "web:5173" in url else {}), timeout=5) as r:
            assert r.status == 200 and json.load(r) == expected
    with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/ready", timeout=5) as r:
        assert r.status == 200
    with urllib.request.urlopen(urllib.request.Request("http://web:5173/", headers={"Host": "localhost:5173"}), timeout=5) as r:
        assert r.status == 200 and "text/html" in r.headers.get("Content-Type", "")
        assert 'id="root"' in r.read().decode()
    print("PASS: direct liveness, database readiness, frontend HTML, Vite proxy")
    '''
            print(call(base + ['exec', '-T', 'api', 'python', '-c', probe]).strip(), flush=True)
            print(call(base + ['exec', '-T', 'db', 'bash', '/opt/agentops/verify-app.sh']).strip(), flush=True)
            sql = ['exec', '-T', 'db', 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'agentops_bootstrap', '-d', 'agentops']
            call(base + sql, data="CREATE SCHEMA closeout_probe; CREATE TABLE closeout_probe.persistence (value text); INSERT INTO closeout_probe.persistence VALUES ('synthetic-restart-marker');")
            call(base + ['restart', 'db'])
            call(base + ['up', '--wait', '--wait-timeout', '120', '--no-recreate', '-d'])
            assert call(base + sql, data='SELECT value FROM closeout_probe.persistence;').strip() == 'synthetic-restart-marker'
            print('PASS: committed marker survives PostgreSQL restart on named volume', flush=True)
            print(call(base + ['exec', '-T', 'api', 'python', '-c', probe]).strip(), flush=True)
            print('All isolated foundation checks passed', flush=True)
        finally:
            call(base + ['stop'], limit=90)
            print('Only this new project stopped; containers, network and named volume retained:', project, flush=True)


if __name__ == "__main__":
    main()
