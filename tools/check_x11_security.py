"""Exercise X SECURITY only on a verified disposable Xvfb, never inherited DISPLAY."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from cyberlab.host_display import helper
from disposable_x11 import disposable_display, disable_core_dumps


def check(executable, repetitions):
    for _attempt in range(repetitions):
        with disposable_display(executable) as (owner, process):
            created = {**owner, **helper({**owner, 'operation': 'generate'})}
            assert helper({**created, 'operation': 'probe'})['ready']
            helper({**owner, 'authorization': created['authorization'], 'operation': 'revoke'})
            for credential in (created, {**owner, 'cookie': '00' * 16}):
                try:
                    helper({**credential, 'operation': 'probe'})
                except ValueError:
                    continue
                raise AssertionError('Invalid/revoked authorization was accepted')
            assert helper({**owner, 'operation': 'probe'})['ready']
            assert process.poll() is None
    print(f'PASS: {repetitions} isolated generate/probe/control-revoke cycles; owner remains usable')


def check_fixture_identity(executable):
    with disposable_display(executable) as (first, first_process), disposable_display(executable) as (second, second_process):
        for forged in ({**first, '_fixture': second['_fixture']},
                       {**first, '_fixture': {**first['_fixture'], 'start_time': 'stale'}}):
            try:
                helper({**forged, 'operation': 'generate'})
            except ValueError:
                continue
            raise AssertionError('Mismatched disposable server identity was accepted')
        assert first['display'] != second['display']
        for owner, process in ((first, first_process), (second, second_process)):
            assert helper({**owner, 'operation': 'probe'})['ready']
            assert process.poll() is None
    print('PASS: wrong socket owner and stale process identity rejected; both fixtures survived')


def check_self_target_revoke(executable):
    with disposable_display(executable) as (owner, process):
        created = {**owner, **helper({**owner, 'operation': 'generate'})}
        assert helper({**created, 'operation': 'revoke'}) == {'ready': True}
        time.sleep(2.2)
        assert process.poll() is None, 'Disposable server crashed during safe revocation or cleanup expiry'
        assert helper({**owner, 'operation': 'probe'})['ready']
        try:
            helper({**created, 'operation': 'probe'})
        except ValueError:
            pass
        else:
            raise AssertionError('Revoked authorization still authenticates')
    print('PASS: self-target revocation switches to a temporary controller; server survives cleanup expiry')


def response(process):
    if not select.select([process.stdout], [], [], 5)[0]:
        raise AssertionError('Owned fixture client did not respond')
    return process.stdout.readline().strip()


@contextmanager
def client(credential, separate_session=True):
    process = subprocess.Popen(['/usr/bin/python3', '-I', str(Path(__file__).with_name('x11_fixture_client.py'))],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, start_new_session=separate_session,
                               preexec_fn=disable_core_dumps)
    try:
        process.stdin.write(json.dumps(credential).encode() + b'\n')
        process.stdin.flush()
        assert response(process) == b'ready'
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


def check_active_clients(executable, repetitions):
    for _attempt in range(repetitions):
        with disposable_display(executable) as (owner, server):
            target = {**owner, **helper({**owner, 'operation': 'generate'})}
            unrelated = {**owner, **helper({**owner, 'operation': 'generate'})}
            with client(target) as first, client(target) as second, client(unrelated) as other, client(owner) as desktop:
                assert helper({**target, 'operation': 'revoke'}) == {'ready': True}
                for closed in (first, second):
                    closed.wait(timeout=5)
                for retained in (other, desktop):
                    assert retained.poll() is None
                    retained.stdin.write(b'ping\n')
                    retained.stdin.flush()
                    assert response(retained) == b'pong'
                assert server.poll() is None
            helper({**unrelated, 'operation': 'revoke'})
            assert helper({**owner, 'operation': 'probe'})['ready']
    print(f'PASS: {repetitions} active-client cleanup cycles; only target windows disconnect')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xvfb', required=True)
    parser.add_argument('--repetitions', type=int, choices=range(1, 11), default=3)
    arguments = parser.parse_args()
    check_fixture_identity(arguments.xvfb)
    check(arguments.xvfb, arguments.repetitions)
    check_self_target_revoke(arguments.xvfb)
    check_active_clients(arguments.xvfb, arguments.repetitions)
