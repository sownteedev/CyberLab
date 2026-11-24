#!/usr/bin/env python3
"""Administrator-run Docker acceptance; only disposable fixture resources."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from cyberlab.lab.workstation import UBUNTU_IMAGE, workstation_user
from cyberlab.policy import RuntimePolicy
from cyberlab.runtime.docker import DockerRuntime
from cyberlab.service import Engine
from cyberlab.session import SessionState
from cyberlab.session.persistence import PracticeStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uid', required=True, type=int)
    arguments = parser.parse_args()
    if os.geteuid() != 0 or arguments.uid <= 0:
        parser.error('Run as administrator with desktop UID; never change Docker access permissions')
    with tempfile.TemporaryDirectory(prefix='cyberlab-machine-setup-', dir='/var/tmp') as directory:
        root = Path(directory)
        project = root / 'catalog/fixture'
        (project / 'assets').mkdir(parents=True)
        (project / 'assets/recipe.txt').write_text('recipe\n')
        (project / 'assets/eggcheck').write_text('#!/bin/sh\ncat /shared_stuff/recipe.txt\n')
        (project / 'assets/notes.txt').write_text('original\n')
        document = {
            'apiVersion': 'cyberlab.ptit/v1', 'kind': 'Lab',
            'metadata': {'id': 'fixture', 'name': 'Disposable account setup acceptance', 'version': '1.0.0', 'tags': ['linux']},
            'nodes': [{'id': 'client', 'image': UBUNTU_IMAGE, 'user': asdict(workstation_user('learner')),
                       'networks': [], 'command': ['sleep', 'infinity'],
                       'files': [{'source': 'assets/notes.txt', 'target': 'notes.txt'}],
                       'resources': {'memory_mb': 512, 'cpu_millicores': 1000},
                       'setup': {
                           'sudo': 'passwordless', 'groups': [{'name': 'bakers', 'gid': 3100}],
                           'users': [{'name': 'frank', 'uid': 3001, 'gid': 3001, 'groups': ['bakers']},
                                     {'name': 'mary', 'uid': 3002, 'gid': 3002, 'sudo': 'passwordless'}],
                           'files': [{'source': 'assets/recipe.txt', 'target': '/shared_stuff/recipe.txt',
                                      'owner': 'frank', 'group': 'bakers', 'mode': '0660'},
                                     {'source': 'assets/eggcheck', 'target': '/usr/local/bin/eggcheck',
                                      'owner': 'root', 'group': 'root', 'mode': '0755'}],
                           'home': [{'path': 'notes.txt', 'owner': 'learner', 'group': 'learner', 'mode': '0600'}],
                       }}], 'networks': [], 'terminals': ['client'],
        }
        (project / 'lab.yaml').write_text(json.dumps(document))
        policy = RuntimePolicy(frozenset({UBUNTU_IMAGE}), workstation_images=frozenset({UBUNTU_IMAGE}))
        runtime = DockerRuntime(workstation_images=policy.workstation_images, checkpoint_scope='setup-' + uuid4().hex)
        store = PracticeStore(root / 'practice.sqlite3')
        engine = Engine(root / 'catalog', policy, runtime, store)
        session = None

        def command(script, user='learner'):
            current = engine.status(session.id, arguments.uid)
            container = runtime._workspace_container(current, current.lab.nodes[0])
            execution = container.exec_run(['/bin/bash', '--noprofile', '--norc', '-c', script], user=user,
                                           environment={'HOME': '/home/' + user, 'USER': user}, workdir='/tmp')
            if execution.exit_code:
                raise RuntimeError('Container assertion failed: ' + execution.output.decode(errors='replace')[-2000:])

        def running(current):
            if current.state != SessionState.RUNNING:
                raise RuntimeError(current.error or 'Session did not reach RUNNING')

        try:
            before = {image.id for image in runtime.client.images.list()}
            session = engine.start('fixture', arguments.uid)
            running(session)
            command('test "$(stat -c %U:%G:%a /shared_stuff/recipe.txt)" = frank:bakers:660 && '
                    'test "$(stat -c %a /home/learner/notes.txt)" = 600 && sudo -n true')
            command('id -nG | grep -qw bakers && test "$(eggcheck)" = recipe && ! sudo -n true', 'frank')
            command('! test -r /shared_stuff/recipe.txt && sudo -n true', 'mary')
            command('test "$(sudo -n getent shadow frank | cut -d: -f2)" = "!"')
            print('PASS: identities, membership, locked password, ownership, modes, sudo and custom executable', flush=True)
            command('printf changed > /shared_stuff/recipe.txt', 'frank')
            command('sudo -n usermod -a -G bakers mary')
            engine.suspend(session.id, arguments.uid)
            engine = Engine(root / 'catalog', policy, runtime, PracticeStore(root / 'practice.sqlite3'))
            running(engine.resume(session.id, arguments.uid))
            command('test "$(cat /shared_stuff/recipe.txt)" = changed && id -nG | grep -qw bakers', 'mary')
            print('PASS: checkpoint resume preserves changed content and group membership', flush=True)
            for iteration in range(2):
                running(engine.reset(session.id, arguments.uid))
                command('test "$(eggcheck)" = recipe', 'frank')
                command('! test -r /shared_stuff/recipe.txt', 'mary')
            after = {image.id for image in runtime.client.images.list()}
            retained = set(engine.practice_store.system_image_ids())
            unexpected = after - before - retained
            if unexpected:
                raise RuntimeError('Unexpected image growth after setup/reset: ' + ', '.join(sorted(unexpected)))
            print('PASS: reset restores declarations; repeated setup creates no software image', flush=True)
        finally:
            if session is not None:
                runtime.remove(session.id)
                store.delete_checkpoint(session.id)
            runtime.system_checkpoints.collect(set())
            runtime.client.close()
        print('CLEANUP: disposable fixture only; production catalog and existing backups untouched')


if __name__ == '__main__':
    main()
