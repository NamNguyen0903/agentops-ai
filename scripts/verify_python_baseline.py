"""Fresh installed-package verification for a completed native candidate set."""
import argparse
import hashlib
import platform
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    args = parser.parse_args()
    repo, candidates = args.repo.resolve(), args.candidates.resolve()
    metadata = json.loads((candidates / 'metadata.json').read_text())
    target = (
        f'py{sys.version_info.major}{sys.version_info.minor}-'
        f'{platform.system().lower()}-{platform.machine().lower()}'
    )

    profiles = {
        'py312-darwin-arm64': ('runtime', 'dev', 'poc-dev'),
        'py311-linux-x86_64': ('dev',),
        'py312-linux-x86_64': ('runtime', 'dev', 'poc-dev'),
        'py312-linux-aarch64': ('runtime', 'dev'),
    }

    if sys.implementation.name != 'cpython' or target not in profiles:
        raise RuntimeError(f'Unsupported target: {target}')

    if metadata['target'] != target:
        raise RuntimeError('Candidate target mismatch')

    if metadata['status'] != 'GENERATED_BINARY_VALIDATED_NOT_ACCEPTED':
        raise RuntimeError('Unexpected candidate status')

    expected = {
        f'{target}-{profile}.txt'
        for profile in profiles[target]
    }

    if {p.name for p in candidates.glob('py*.txt')} != expected:
        raise RuntimeError('Missing or unexpected candidate profiles')

    if not expected <= set(metadata['hashes']):
        raise RuntimeError('Missing candidate checksums')

    for name, digest in metadata['hashes'].items():
        if Path(name).name != name:
            raise RuntimeError('Invalid checksum filename')

        actual = hashlib.sha256(
            (candidates / name).read_bytes()
        ).hexdigest()

        if actual != digest:
            raise RuntimeError(f'Checksum mismatch: {name}')

    source_work = Path(metadata['workspace'])
    work = Path(tempfile.mkdtemp(prefix='agentops-baseline-verify-'))
    print(f'VERIFICATION_WORKSPACE={work}', flush=True)
    env = {'HOME': str(work), 'PATH': '/usr/local/bin:/usr/bin:/bin',
           'PIP_CONFIG_FILE': os.devnull, 'PIP_NO_INDEX': '1',
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
           'AGENTOPS_RUN_DB_INTEGRATION': '0', 'AGENTOPS_RUN_LEGACY_COMPOSE_TESTS': '0',
           'AGENTOPS_AUTH_REVIEW_ENABLED': 'false'}
    results = []

    def run(command, label, allowed=(0,)):
        output = subprocess.run(command, cwd=work, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (work / f'{label}.log').write_text(output.stdout)
        results.append({'label': label, 'command': [str(x) for x in command],
                        'exit': output.returncode, 'output': output.stdout})
        (work / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        print(f'{label}: exit={output.returncode}\n{output.stdout[-1300:]}', flush=True)
        if output.returncode not in allowed:
            raise RuntimeError(label)

    for lock in sorted(candidates.glob('py*.txt')):
        profile = 'poc' if '-poc-dev' in lock.name else ('runtime' if '-runtime' in lock.name else 'dev')
        directory = repo / ('experiments/auth-authlib-oidc' if profile == 'poc' else 'apps/api')
        destination = work / f'source-{profile}'
        destination.mkdir()
        shutil.copy2(directory / 'pyproject.toml', destination / 'pyproject.toml')
        shutil.copytree(directory / 'src', destination / 'src',
                        ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
        run([sys.executable, '-m', 'venv', work / profile], profile + '-venv')
        python = work / profile / 'bin/python'
        run([python, '-m', 'pip', 'install', '--only-binary=:all:', '--require-hashes',
             '--find-links', source_work / f'wheels-{profile}', '-r', lock], profile + '-install')
        run([python, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation',
             str(destination) + ('' if profile == 'runtime' else '[dev]')], profile + '-package')
        run([python, '-m', 'pip', 'check'], profile + '-check')
        run([python, '-m', 'pip', 'list', '--format=json'], profile + '-versions')
        installed = {re.sub(r'[-_.]+', '-', x['name']).lower(): x['version']
                     for x in json.loads(results[-1]['output'])}
        for name, version in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)', lock.read_text(), re.M):
            if installed.get(re.sub(r'[-_.]+', '-', name).lower()) != version:
                raise RuntimeError(f'Installed version mismatch: {name}')
        if profile == 'runtime':
            if 'pytest' in installed:
                raise RuntimeError('Runtime unexpectedly contains pytest')
        else:
            run([python, '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--tb=short',
                 directory / 'tests'], profile + '-pytest')
            if profile == 'poc':
                run([python, '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--tb=short',
                     '--runxfail', '-k', 'stock_debug_must_not_disclose_verifier',
                     directory / 'tests'], 'poc-stock-security-fail', allowed=(1,))
    if 'poc-dev' in profiles[target]:
        result = next(
            r for r in results
            if r['label'] == 'poc-stock-security-fail'
        )

        diagnostic = (
            'PKCELogExposure: '
            'Stock Authlib emitted PKCE secret at DEBUG'
        )

        if diagnostic not in result['output']:
            raise RuntimeError(
                'Forced XFAIL did not establish expected PKCE exposure'
            )

    print('VERIFIED_FRESH_INSTALLS_WITHIN_SCOPE', flush=True)


if __name__ == '__main__':
    main()
