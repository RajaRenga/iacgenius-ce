"""IaC Genius Community Edition — Spot host bootstrap.

Borrows the RemediGenius-CE boot mechanics: disposable instance, S3 holds the durable Hermes
home, the pinned Hermes image runs with no AWS credentials, the model key comes from Secrets
Manager. The stdlib-only iacg desk runs as a systemd service on the host; Hermes reaches it
through the Unix socket mounted into the container. Generation needs no AWS read credentials.
"""
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path('/opt/iacgenius')
SOURCE = ROOT / 'source'
PACKAGE = ROOT / 'package'
UID = 10000
HERMES_HOME = Path('/data/hermes')
DESK_HOME = Path('/data/iacg')
# Generated mission code lives here, writable by the agent. DESK_HOME stays read-only in the
# container so the agent can read desk state but never mutate the deterministic store.
WORK_HOME = Path('/data/iacg-work')
DESK_RUNDIR = Path('/run/iacg')
DESK_SOCKET = DESK_RUNDIR / 'desk.sock'
PROFILE = 'iacgenius'
CONTAINER = 'iacgenius'
NETWORK = 'iacgenius'
SUBNET = '172.30.0.0/24'
PORT = 9126
LOGIN = HERMES_HOME / 'iacgenius-login.json'
RUNDIR = Path('/run/iacgenius')


def run(*args, **kw):
    return subprocess.run(args, check=True, text=True, **kw)


def ensure_user():
    if subprocess.run(['getent', 'group', str(UID)], capture_output=True).returncode:
        run('groupadd', '--system', '--gid', str(UID), 'iacgenius')
    if subprocess.run(['getent', 'passwd', str(UID)], capture_output=True).returncode:
        run('useradd', '--system', '--uid', str(UID), '--gid', str(UID), '--no-create-home', '--shell', '/sbin/nologin',
            'iacgenius')


def durable_url(cfg):
    return f"s3://{cfg['bucket']}/state"


def restore_state(cfg):
    for home, name in ((HERMES_HOME, 'hermes'), (DESK_HOME, 'iacg')):
        home.mkdir(parents=True, exist_ok=True)
        os.chown(home, UID, UID)
        if any(home.iterdir()):
            print(f'{name} state already present; not restoring over it')
            continue
        archive = ROOT / f'{name}-state.tar.gz'
        got = subprocess.run(['aws', 's3', 'cp', f"{durable_url(cfg)}/{name}.tar.gz", str(archive),
                              '--region', cfg['region'], '--only-show-errors'], capture_output=True, text=True)
        if got.returncode == 0 and archive.exists():
            run('tar', '-xzf', str(archive), '-C', str(home))
            if home == DESK_HOME:
                run('chown', '-R', f'{UID}:{UID}', str(home))
            print(f'restored {name} state from S3')
        else:
            print(f'no prior {name} state in S3; starting fresh')
    DESK_RUNDIR.mkdir(parents=True, exist_ok=True)
    os.chown(DESK_RUNDIR, UID, UID)


def network():
    if subprocess.run(['docker', 'network', 'inspect', NETWORK], capture_output=True).returncode:
        run('docker', 'network', 'create', '--subnet', SUBNET, NETWORK)
    # Best-effort container egress hardening: HTTPS only, no metadata, no private ranges.
    # The security group and IMDSv2 hop limit 1 already protect the instance; this is defense in depth.
    chain = 'IACGENIUS'
    if subprocess.run(['iptables', '-n', '-L', chain], capture_output=True).returncode:
        subprocess.run(['iptables', '-N', chain], check=False)
    for line in Path('/etc/resolv.conf').read_text().splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == 'nameserver' and ':' not in fields[1]:
            for protocol in ('udp', 'tcp'):
                subprocess.run(['iptables', '-A', chain, '-d', fields[1], '-p', protocol, '--dport', '53', '-j', 'ACCEPT'], check=False)
    for dest in ('169.254.0.0/16', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8'):
        subprocess.run(['iptables', '-A', chain, '-d', dest, '-j', 'DROP'], check=False)
    for port in ('443', '80'):
        subprocess.run(['iptables', '-A', chain, '-p', 'tcp', '--dport', port, '-j', 'ACCEPT'], check=False)
    subprocess.run(['iptables', '-A', chain, '-j', 'DROP'], check=False)
    args = ['-s', SUBNET, '-j', chain]
    if subprocess.run(['iptables', '-C', 'DOCKER-USER', *args], capture_output=True).returncode:
        subprocess.run(['iptables', '-I', 'DOCKER-USER', '1', *args], check=False)


def seed_model(config_text, model_seed):
    if model_seed:
        name, base_url = model_seed
        return config_text.replace('__MODEL_NAME__', json.dumps(name)).replace('__MODEL_BASE_URL__', json.dumps(base_url))
    out, skipping = [], False
    for line in config_text.splitlines(keepends=True):
        if line.startswith('model:'):
            skipping = True
            continue
        if skipping and (line.startswith((' ', '\t')) or not line.strip()):
            continue
        skipping = False
        out.append(line)
    return ''.join(out)


def hermes_env(cfg, model_key):
    if not LOGIN.exists():
        LOGIN.write_text(json.dumps({'username': 'owner', 'password': secrets.token_urlsafe(24), 'secret': secrets.token_hex(32)}))
        LOGIN.chmod(0o600)
        os.chown(LOGIN, UID, UID)
    login = json.loads(LOGIN.read_text())
    values = {'HERMES_DASHBOARD': '1', 'HERMES_DASHBOARD_PORT': str(PORT),
              'HERMES_DASHBOARD_BASIC_AUTH_USERNAME': login['username'],
              'HERMES_DASHBOARD_BASIC_AUTH_PASSWORD': login['password'],
              'HERMES_DASHBOARD_BASIC_AUTH_SECRET': login['secret'],
              'AWS_EC2_METADATA_DISABLED': 'true',
              # The agent may write generated code into the mission workspace as well as its home.
              'HERMES_WRITE_SAFE_ROOT': f'/opt/data:{WORK_HOME.as_posix()}'}
    if model_key:
        values['MODEL_API_KEY'] = model_key
    if any('\n' in v or '\r' in v for v in values.values()):
        raise ValueError('Invalid credential shape')
    RUNDIR.mkdir(exist_ok=True, mode=0o700)
    path = RUNDIR / 'hermes.env'
    path.write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
    path.chmod(0o600)


def in_container(*args, check=True, **kw):
    return subprocess.run(['docker', 'exec', '--user', f'{UID}:{UID}', CONTAINER, *args], check=check, text=True, **kw)


def seed_model_key():
    in_container('python', '-c', f'''
import os
from pathlib import Path
p = Path('/opt/data/profiles/{PROFILE}/.env')
s = p.read_text() if p.exists() else ''
key = os.environ.get('MODEL_API_KEY', '')
if key and not any(l.startswith('MODEL_API_KEY=') for l in s.splitlines()):
    p.write_text(s.rstrip() + ('\\n' if s.strip() else '') + 'MODEL_API_KEY=' + key + '\\n')
    p.chmod(0o600)
''')


def sync_profile():
    package = SOURCE / 'profiles' / PROFILE
    profile = HERMES_HOME / 'profiles' / PROFILE
    profile.mkdir(parents=True, exist_ok=True)
    shutil.copy2(package / 'SOUL.md', profile / 'SOUL.md')
    shutil.copy2(package / 'BUILD-BRIEF.md', profile / 'BUILD-BRIEF.md')
    for sub in ('skills', 'plugins', 'dashboard-plugins'):
        src = package / sub
        if not src.exists():
            continue
        dst = profile / sub
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', 'local.json'))
    (profile / 'plugins' / 'iacg-desk' / 'local.json').write_text(json.dumps(
        {'socket': DESK_SOCKET.as_posix(), 'home': DESK_HOME.as_posix()}))
    board_local = json.dumps({'socket': DESK_SOCKET.as_posix(), 'board': (DESK_HOME / 'board.html').as_posix(),
                              'status': (DESK_HOME / 'board.json').as_posix()})
    (profile / 'dashboard-plugins' / 'iacg-board' / 'local.json').write_text(board_local)
    # Hermes serves user dashboard plugins from the home plugins dir too (mirror RGCE).
    tab = HERMES_HOME / 'plugins' / 'iacg-board'
    if tab.exists():
        shutil.rmtree(tab)
    shutil.copytree(package / 'dashboard-plugins' / 'iacg-board', tab,
                    ignore=shutil.ignore_patterns('__pycache__', 'local.json'))
    (tab / 'local.json').write_text(board_local)
    # Dashboard plugin discovery is profile-scoped: the board must also live in the profile's own
    # plugins dir, or the tab is invisible when the dashboard is opened on that profile.
    profile_tab = profile / 'plugins' / 'iacg-board'
    if profile_tab.exists():
        shutil.rmtree(profile_tab)
    shutil.copytree(package / 'dashboard-plugins' / 'iacg-board', profile_tab,
                    ignore=shutil.ignore_patterns('__pycache__', 'local.json'))
    (profile_tab / 'local.json').write_text(board_local)
    for path in [profile, *profile.rglob('*'), tab, *tab.rglob('*')]:
        if hasattr(os, 'lchown'):
            os.lchown(path, UID, UID)
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else (0o600 if path.name == '.env' else 0o644))


DESK_CODE = Path('/opt/iacg/src')


def install_desk_code():
    # /opt/iacgenius is 0700 root; the desk (uid 10000) needs its code in a readable place.
    DESK_CODE.mkdir(parents=True, exist_ok=True)
    dst = DESK_CODE / 'iacg_desk'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SOURCE / 'iacg_desk', dst, ignore=shutil.ignore_patterns('__pycache__'))
    run('chown', '-R', f'{UID}:{UID}', '/opt/iacg')
    run('chmod', '-R', 'u+rwX,go+rX', '/opt/iacg')
    # The provider cache must be writable by the desk user (a root-owned plugins dir blocks init).
    (DESK_HOME / 'plugins').mkdir(parents=True, exist_ok=True)
    run('chown', '-R', f'{UID}:{UID}', str(DESK_HOME))
    # Writable workspace for generated mission code (the agent writes here, not into read-only DESK_HOME).
    WORK_HOME.mkdir(parents=True, exist_ok=True)
    run('chown', '-R', f'{UID}:{UID}', str(WORK_HOME))


def install_toolchain():
    # The validation toolchain must exist on the host. Install at boot so a relaunch is reproducible;
    # previously this was a manual step and did not survive a relaunch from the base AMI.
    if shutil.which('terraform') and shutil.which('tflint') and shutil.which('checkov'):
        return
    script = SOURCE / 'toolchain' / 'install-toolchain.sh'
    if script.exists():
        run('bash', str(script))


def desk_unit():
    return f'''[Unit]
Description=IaC Genius CE desk (stdlib only, Unix socket API, no AWS credentials)
After=network-online.target
[Service]
User={UID}
Group={UID}
Environment=PYTHONPATH={DESK_CODE.as_posix()}
Environment=IACG_HOME={DESK_HOME.as_posix()}
Environment=TF_PLUGIN_CACHE_DIR={DESK_HOME.as_posix()}/plugins
Environment=PATH=/usr/local/bin:/usr/bin:/bin
RuntimeDirectory=iacg
RuntimeDirectoryMode=0750
RuntimeDirectoryPreserve=yes
ExecStart=/usr/bin/python3 -m iacg_desk serve --socket {DESK_SOCKET.as_posix()}
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
'''


def hermes_unit(cfg):
    memory = int(cfg.get('container_memory_mb', 6144))
    return f'''[Unit]
Description=IaC Genius CE Hermes (pinned image, no AWS credentials)
After=docker.service iacg-desk.service
Wants=iacg-desk.service
Requires=docker.service
[Service]
ExecStartPre=/bin/sh -c 'n=0; while [ ! -S {DESK_SOCKET.as_posix()} ] && [ $$n -lt 60 ]; do n=$$((n+1)); sleep 1; done; exit 0'
ExecStartPre=-/usr/bin/docker rm -f {CONTAINER}
ExecStart=/usr/bin/docker run --rm --name {CONTAINER} --network {NETWORK} --env-file {RUNDIR.as_posix()}/hermes.env -p 127.0.0.1:{PORT}:{PORT} -v {HERMES_HOME.as_posix()}:/opt/data -v {DESK_RUNDIR.as_posix()}:{DESK_RUNDIR.as_posix()} -v {DESK_HOME.as_posix()}:{DESK_HOME.as_posix()}:ro -v {WORK_HOME.as_posix()}:{WORK_HOME.as_posix()} -v {PACKAGE.as_posix()}:/opt/iacgenius-package:ro --memory {memory}m --pids-limit 1024 {cfg['image']} gateway run
ExecStop=/usr/bin/docker stop -t 30 {CONTAINER}
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
'''


CHECKPOINT = '''#!/bin/bash
set -euo pipefail
tar -czf /opt/iacgenius/hermes-state.tar.gz -C /data/hermes .
aws s3 cp /opt/iacgenius/hermes-state.tar.gz s3://__BUCKET__/state/hermes.tar.gz --region __REGION__ --only-show-errors
tar -czf /opt/iacgenius/iacg-state.tar.gz -C /data/iacg .
aws s3 cp /opt/iacgenius/iacg-state.tar.gz s3://__BUCKET__/state/iacg.tar.gz --region __REGION__ --only-show-errors
'''


def checkpoint_units(cfg):
    script = Path('/opt/iacgenius/checkpoint.sh')
    script.write_text(CHECKPOINT.replace('__BUCKET__', cfg['bucket']).replace('__REGION__', cfg['region']))
    script.chmod(0o755)
    return {
        'iacgenius-checkpoint.service': f'''[Unit]
Description=IaC Genius CE Hermes home + desk state checkpoint to S3
[Service]
Type=oneshot
ExecStart={script.as_posix()}
''',
        'iacgenius-checkpoint.timer': '''[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
''',
    }


def main():
    cfg = json.loads((ROOT / 'config.json').read_text())
    ensure_user()
    restore_state(cfg)
    network()
    model_key = ''
    if cfg.get('model_secret'):
        model_key = run('aws', 'secretsmanager', 'get-secret-value', '--secret-id', cfg['model_secret'], '--region',
                        cfg['region'], '--query', 'SecretString', '--output', 'text', capture_output=True).stdout.strip()
    hermes_env(cfg, model_key)
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    shutil.copytree(SOURCE / 'profiles' / PROFILE, PACKAGE, ignore=shutil.ignore_patterns('__pycache__'))
    config = PACKAGE / 'config.yaml'
    config.write_text(seed_model(config.read_text(), (cfg['model_name'], cfg['model_base_url']) if model_key else None))
    install_desk_code()
    install_toolchain()
    units = {'iacg-desk.service': desk_unit(), 'iacgenius-hermes.service': hermes_unit(cfg), **checkpoint_units(cfg)}
    for name, body in units.items():
        Path('/etc/systemd/system', name).write_text(body)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'iacg-desk.service', 'iacgenius-hermes.service', 'iacgenius-checkpoint.timer')
    run('systemctl', 'restart', 'iacg-desk.service')
    for _ in range(60):
        if DESK_SOCKET.exists():
            break
        time.sleep(1)
    else:
        raise RuntimeError('iacg-desk did not start; check journalctl -u iacg-desk')
    run('systemctl', 'restart', 'iacgenius-hermes.service')
    for _ in range(120):
        if in_container('test', '-f', '/opt/data/config.yaml', check=False, capture_output=True).returncode == 0:
            break
        time.sleep(2)
    else:
        raise RuntimeError('Hermes container did not initialize; check journalctl -u iacgenius-hermes')
    if not (HERMES_HOME / 'profiles' / PROFILE).exists():
        subprocess.run(['docker', 'exec', CONTAINER, 'hermes', 'profile', 'install', '/opt/iacgenius-package',
                        '--name', PROFILE, '--yes'], check=True)
    sync_profile()
    seed_model_key()
    in_container('hermes', 'profile', 'use', PROFILE)
    run('docker', 'restart', CONTAINER)
    run('systemctl', 'start', 'iacgenius-checkpoint.timer')
    print('IaC Genius CE ready. Dashboard: SSM tunnel to 127.0.0.1:%d; login in %s.' % (PORT, LOGIN))
    print('Next: open the dashboard, say "read BUILD-BRIEF.md and start building"; the iacg desk is already running.')


if __name__ == '__main__':
    main()