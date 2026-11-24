"""Generate native, hash-checked candidates; never overwrite accepted locks.

Run with the target interpreter. All environments/builds live in a new temporary
directory. Only a completely downloaded candidate set is copied to --output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output.resolve()
    target = f'py{sys.version_info.major}{sys.version_info.minor}-{platform.system().lower()}-{platform.machine().lower()}'
    profiles = {
        'py312-darwin-arm64': ('runtime', 'dev', 'poc'),
        'py311-linux-x86_64': ('dev',),
        'py312-linux-x86_64': ('runtime', 'dev', 'poc'),
        'py312-linux-aarch64': ('runtime', 'dev'),
    }
    if sys.implementation.name != 'cpython' or target not in profiles:
        parser.error(f'Unsupported target: {target}')
    if output.exists():
        parser.error('Output must not exist; preserve prior candidates')
    work = Path(tempfile.mkdtemp(prefix='agentops-baseline-'))
    print(f'WORKSPACE={work} TARGET={target}', flush=True)
    (work / 'STATUS').write_text('IN_PROGRESS\n')
    home = work / 'home'
    home.mkdir()
    env = {
        'HOME': str(home), 'PATH': '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
        'PIP_CONFIG_FILE': os.devnull, 'PIP_INDEX_URL': 'https://pypi.org/simple',
        'PIP_ONLY_BINARY': ':all:', 'PIP_KEYRING_PROVIDER': 'disabled',
        'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PYTHONDONTWRITEBYTECODE': '1',
    }

    def run(command, cwd=work):
        print('COMMAND:', json.dumps([str(x) for x in command]), flush=True)
        with (work / 'commands.log').open('a') as log:
            log.write(json.dumps([str(x) for x in command]) + '\n')
            result = subprocess.run(command, cwd=cwd, env=env, stdout=log,
                                    stderr=subprocess.STDOUT)
            log.write(f'EXIT={result.returncode}\n')
        if result.returncode:
            print((work / 'commands.log').read_text()[-6000:], flush=True)
            raise RuntimeError(f'Command failed: {result.returncode}')

    def pins(path):
        result = {}
        text = path.read_text().replace('\\\n', ' ')
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            requirement = line.split(' --hash=', 1)[0].strip()
            # Native outputs must be simple exact pins. Fail rather than silently
            # lose markers, URLs, extras or additional pip directives.
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)', requirement)
            if not match:
                raise ValueError(f'Unexpected generated requirement: {requirement}')
            name = re.sub(r'[-_.]+', '-', match[1]).lower()
            if name in result and result[name] != match[2]:
                raise ValueError('Conflicting generated pin')
            result[name] = match[2]
        if not result:
            raise ValueError('Empty resolution')
        return result

    try:
        seed = work / 'seed.txt'
        shutil.copy2(repo / 'requirements/python-baseline-seed.txt', seed)
        for name, source in [('api', repo / 'apps/api'), ('poc', repo / 'experiments/auth-authlib-oidc')]:
            destination = work / name
            destination.mkdir()
            shutil.copy2(source / 'pyproject.toml', destination / 'pyproject.toml')
            shutil.copytree(source / 'src', destination / 'src',
                            ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
        run([sys.executable, '-m', 'venv', work / 'generator'])
        python = work / 'generator/bin/python'
        run([python, '-m', 'pip', 'install', '-c', seed,
             'pip==26.3', 'pip-tools==7.7.0', 'setuptools==84.1.0', 'wheel'])
        run([python, '-m', 'pip', 'check'])
        snapshot = subprocess.check_output([python, '-m', 'pip', 'freeze', '--all'], env=env)
        toolpins = work / 'generator-pins.txt'
        toolpins.write_bytes(snapshot)
        common = [python, '-m', 'piptools', 'compile', '--no-config',
                  '--resolver=backtracking', '--allow-unsafe', '--strip-extras',
                  '--generate-hashes', '--no-header', '--no-annotate',
                  '--no-emit-options', '--no-build-isolation',
                  '--pip-args=--only-binary=:all:', '--cache-dir', str(work / 'cache')]
        candidate = work / 'candidate'
        candidate.mkdir()
        run(common + ['-o', candidate / 'generator.lock.txt', toolpins])
        # Retain complete hashed generator artifacts for replay without trusting
        # an unconstrained bootstrap. First bootstrap itself is not prelocked.
        run([python, '-m', 'pip', 'download', '--require-hashes',
             '-r', candidate / 'generator.lock.txt', '-d', work / 'generator-wheels'])
        runtime_pins = None
        for profile in profiles[target]:
            project = 'poc' if profile == 'poc' else 'api'
            filename = f'{target}-{"poc-dev" if profile == "poc" else profile}.txt'
            lock = candidate / filename
            command = common + ['--all-build-deps', '-c', seed, '-c', toolpins]
            if profile != 'runtime':
                command += ['--extra=dev']
            if profile == 'dev' and runtime_pins:
                command += ['-c', runtime_pins]
            command += ['-o', lock, 'pyproject.toml']
            run(command, work / project)
            resolved = pins(lock)
            if profile == 'runtime':
                runtime_pins = work / 'runtime-pins.txt'
                runtime_pins.write_text(''.join(f'{n}=={v}\n' for n, v in sorted(resolved.items())))
            elif profile == 'dev' and runtime_pins:
                if not pins(runtime_pins).items() <= resolved.items():
                    raise ValueError('Runtime/dev version divergence')
            run([python, '-m', 'pip', 'download', '--require-hashes',
                 '-r', lock, '-d', work / f'wheels-{profile}'])
        shutil.copy2(toolpins, candidate / toolpins.name)
        shutil.copy2(seed, candidate / seed.name)
        metadata = {'target': target, 'python': sys.version, 'platform': platform.platform(),
                    'workspace': str(work), 'status': 'GENERATED_BINARY_VALIDATED_NOT_ACCEPTED',
                    'hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(candidate.glob('*.txt'))}}
        (candidate / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.with_name(output.name + '.partial')
        if staging.exists():
            raise ValueError('Partial output exists; use a new destination')
        shutil.copytree(candidate, staging)
        staging.rename(output)
        (work / 'STATUS').write_text('GENERATED_BINARY_VALIDATED_NOT_ACCEPTED\n')
        print(f'CANDIDATES={output}', flush=True)
    except BaseException:
        (work / 'STATUS').write_text('FAILED_NOT_ACCEPTED\n')
        raise


if __name__ == '__main__':
    main()
