#!/usr/bin/env python3
"""Explicit administrator acceptance with disposable catalog, images and Sessions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import argparse
import asyncio
from dataclasses import asdict
import json
import os
import tempfile
import re
from time import monotonic, sleep
from uuid import uuid4

from tools.tests.unit import check_workstations as fixture
from cyberlab.authoring.service import Authoring
from cyberlab.authoring.software import SoftwarePreparation
from cyberlab.runtime.docker_desktop import DockerDesktopStream

def verify_binary_transport(runtime, container):
    execution = runtime.client.api.exec_create(container.id,
        cmd=['/usr/bin/python3', '-I', '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read(65536))'],
        stdin=True, stdout=True, stderr=False, tty=False, privileged=False, user='learner')
    connection = runtime.client.api.exec_start(execution['Id'], tty=False, socket=True)
    stream = DockerDesktopStream(runtime.client.api, execution['Id'], connection)
    payload = bytes(range(256)) * 256
    pending = payload
    output = bytearray()
    deadline = monotonic() + 10
    try:
        while monotonic() < deadline:
            if pending:
                pending = pending[stream.write(pending):]
            chunk, ended = stream.read(65536)
            output.extend(chunk)
            if ended:
                assert not pending and bytes(output) == payload, 'Docker corrupted binary display data'
                print('PASS: real Docker transports all binary bytes including repeated detach sequences', flush=True)
                return
            sleep(.005)
        raise AssertionError('Binary display round trip timed out')
    finally:
        stream.close()

def terminal_command(runtime, session, script, timeout=40):
    terminal = runtime.open_terminal(session, 'client')
    try:
        data = ('stty -echo\n' + script + '\nprintf "\\nCYBERLAB_%s:%s\\n" COMMAND_DONE "$?"\n').encode()
        while data:
            data = data[terminal.write(data):]
        output = bytearray()
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            chunk, ended = terminal.read(65536)
            output.extend(chunk)
            match = re.search(rb'\r?\nCYBERLAB_COMMAND_DONE:(\d+)\r?\n', output)
            if match:
                assert match[1] == b'0', output.decode(errors='replace')[-2048:]
                terminal.write(b'exit\n')
                return output.decode(errors='replace')
            assert not ended, 'Terminal exited before completing fixture command'
            assert len(output) <= 1024 * 1024, 'Fixture terminal output too large'
            sleep(.02)
        raise AssertionError('Fixture terminal command timed out')
    finally:
        terminal.close()

def verify(uid, display=None):
    if display:
        from cyberlab.runtime import desktop
        desktop.SETUP = desktop.SETUP.replace('stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True',
            "stdout=(root / 'fixture-server.log').open('ab'), stderr=subprocess.STDOUT, start_new_session=True")
        desktop.SETUP = desktop.SETUP.replace("'--session-name=CyberLab ' + sys.argv[2]", "'--session-name=CyberLab ' + sys.argv[2], '--debug=window'")
    scope = 'software-acceptance-' + uuid4().hex
    with tempfile.TemporaryDirectory(prefix='cyberlab-software-acceptance-', dir='/var/tmp') as directory:
        root = Path(directory)
        catalog = root / 'catalog'
        catalog.mkdir()
        runtime = fixture.DockerRuntime(workstation_images={fixture.UBUNTU_IMAGE}, checkpoint_scope=scope)
        policy = fixture.RuntimePolicy(frozenset({fixture.UBUNTU_IMAGE}), workstation_images=frozenset({fixture.UBUNTU_IMAGE}))
        engine = fixture.Engine(catalog, policy, runtime, fixture.PracticeStore(root / 'practice.sqlite3'))
        authoring = Authoring(root / 'drafts.sqlite3', catalog, policy, engine._lock)
        manager = SoftwarePreparation(root / 'software.sqlite3', authoring, runtime.software,
                                      active_images=engine.software_image_ids)
        authoring.software = manager
        runtime.prepared_software = manager
        sessions = []

        def software_images():
            return {image.id for image in runtime.client.images.list(filters={'label': [
                'org.ptit.cyberlab.software.scope=' + scope]})
                if 'org.ptit.cyberlab.checkpoint' not in (image.attrs.get('Config', {}).get('Labels') or {})}

        def checkpoint_images():
            return {image.id for image in runtime.client.images.list(filters={'label': [
                'org.ptit.cyberlab.checkpoint-scope=' + scope, 'org.ptit.cyberlab.checkpoint=v1']})}

        try:
            draft = authoring.create('software-fixture', 'Disposable software acceptance', uid, tags=['linux'])
            document = fixture.definition()
            document['metadata']['tags'] = ['linux']
            document['metadata']['id'] = 'software-fixture'
            document['networks'] = [{'id': 'lan'}]
            peer = fixture.definition()['nodes'][0]
            peer.update(id='peer', networks=['lan'])
            document['nodes'].append(peer)
            document['nodes'][0].update(networks=['lan'], software={'gui': True, 'apps': ['wireshark', 'firefox'], 'packages': ['xdotool'] if display else []}, resources={'memory_mb': 2048, 'cpu_millicores': 2000})
            document['nodes'][0]['user'] = asdict(fixture.workstation_user('learner'))
            draft = authoring.save(draft['id'], draft['revision'], json.dumps(document), uid)
            started = monotonic()
            job = manager.prepare(draft['id'], draft['revision'], 'client', uid)
            previous = ''
            while job['state'] in {'QUEUED', 'PREPARING', 'CANCELLING'}:
                if job['message'] != previous:
                    print(job['message'], flush=True)
                    previous = job['message']
                sleep(1)
                job = manager.get(job['id'], uid)
            assert job['state'] == 'READY', job.get('error')
            prepared_images = software_images()
            assert prepared_images == {job['environment']}, prepared_images
            print(f'PASS: prepared Firefox/Wireshark in {monotonic()-started:.1f}s', flush=True)
            draft = manager.apply(job['id'], uid)
            result = authoring.publish(draft['id'], draft['revision'], draft['digest'], uid)
            assert result['published'], result
            session = engine.start('software-fixture', uid)
            sessions.append(session.id)
            if session.state != fixture.SessionState.RUNNING:
                for container in runtime._resources(runtime.client.containers, session.id, include_stopped=True):
                    print('Container diagnostic:', container.status, container.logs(tail=80).decode(errors='replace'), flush=True)
                raise AssertionError(session.error)
            container = runtime._workspace_container(session, session.lab.nodes[0])
            verify_binary_transport(runtime, container)
            def command(script, user='learner'):
                result = container.exec_run(['/bin/bash', '-c', script], user=user, environment={'HOME': '/home/learner', 'DISPLAY': ':99', 'XAUTHORITY': '/tmp/cyberlab-apps/Xauthority'})
                assert result.exit_code == 0, result.output.decode(errors='replace')[-4096:]
                return result.output.decode(errors='replace')
            print(terminal_command(runtime, session, 'id; firefox --version; wireshark --version | head -2; dumpcap -D'), flush=True)
            print('PASS: actual CyberLab terminal retains capture groups with custom username', flush=True)
            terminal_command(runtime, session, 'dumpcap -i any -a duration:4 -w /home/learner/fixture.pcap >/tmp/capture-check.log 2>&1 & capture=$!; sleep 1; ping -c 2 peer >/dev/null; wait "$capture" && tshark -r /home/learner/fixture.pcap -Y icmp | grep -q ICMP')
            print('PASS: non-root capture between two Lab machines, saved PCAP and ICMP filtering', flush=True)
            peer_container = runtime._workspace_container(session, session.lab.nodes[1])
            assert 'NET_ADMIN' not in peer_container.attrs['HostConfig']['CapAdd']
            assert not engine.desktop_status(session.id, 'peer', uid)['auto_connect']
            runtime.software.cleanup()
            assert runtime.running(session), 'Preparation cleanup must never remove practice containers'
            assert engine.desktop_status(session.id, 'client', uid)['ready']
            handle, _ = engine.open_desktop(session.id, 'client', uid, ':software-fixture')
            engine.desktop('close', handle, uid, ':software-fixture')
            command('timeout 12 firefox --headless --screenshot /tmp/firefox-fixture.png about:blank > /tmp/firefox-check.log 2>&1 || { cat /tmp/firefox-check.log; exit 1; }; test -s /tmp/firefox-fixture.png')
            print('PASS: Firefox renders with sandbox enabled (no --no-sandbox)', flush=True)
            if display:
                from tools.tests.runtime.check_software_gui import verify_gui
                asyncio.run(verify_gui(engine, runtime, session, uid, display, terminal_command))
            command('touch /home/learner/acceptance-only')
            engine.save(session.id, uid)
            previous_checkpoints = engine.practice_store.system_image_ids()
            assert checkpoint_images() == previous_checkpoints
            engine.save(session.id, uid)
            current_checkpoints = engine.practice_store.system_image_ids()
            assert current_checkpoints.isdisjoint(previous_checkpoints)
            assert checkpoint_images() == current_checkpoints, 'Repeated save retained unused checkpoint images'
            engine.stop(session.id, uid)
            resumed = engine.resume(session.id, uid)
            assert resumed.state == fixture.SessionState.RUNNING, resumed.error
            container = runtime._workspace_container(resumed, resumed.lab.nodes[0])
            command('test -f /home/learner/acceptance-only; command -v wireshark; command -v firefox')
            paused = engine.suspend(session.id, uid)
            assert paused.state == fixture.SessionState.SUSPENDED
            assert checkpoint_images() == engine.practice_store.system_image_ids()
            continued = engine.resume(session.id, uid)
            assert continued.state == fixture.SessionState.RUNNING
            reset = engine.reset(session.id, uid)
            assert reset.state == fixture.SessionState.RUNNING, reset.error
            assert not checkpoint_images(), 'Reset retained discarded checkpoint images'
            assert software_images() == prepared_images, 'Reset rebuilt unchanged software'
            container = runtime._workspace_container(reset, reset.lab.nodes[0])
            command('test ! -e /home/learner/acceptance-only; command -v wireshark; command -v firefox')
            engine.stop(session.id, uid)
            fresh = engine.start('software-fixture', uid)
            sessions.append(fresh.id)
            assert fresh.state == fixture.SessionState.RUNNING, fresh.error
            container = runtime._workspace_container(fresh, fresh.lab.nodes[0])
            command('test ! -e /home/learner/acceptance-only; command -v wireshark; command -v firefox')
            assert software_images() == prepared_images, 'Fresh Session duplicated prepared software'
            for attempt in range(3):
                engine.stop(fresh.id, uid)
                fresh = engine.reset(fresh.id, uid)
                assert fresh.state == fixture.SessionState.RUNNING, fresh.error
                assert software_images() == prepared_images
                assert not checkpoint_images()
            print('PASS: saved work retained; fresh Session has applications without personal files', flush=True)
            print('PASS: repeated save replaces unused checkpoints; start/reset reuse prepared software without image growth', flush=True)
        finally:
            manager.shutdown()
            for identifier in sessions:
                engine._close_attachments(identifier)
                runtime.remove(identifier)
            runtime.system_checkpoints.collect(set())
            runtime.software.cleanup()
            for image in runtime.client.images.list(filters={'label': ['org.ptit.cyberlab.software.scope=' + scope]}):
                runtime.client.images.remove(image.id, force=False, noprune=True)
            runtime.client.close()
            print('CLEANUP: only disposable test resources removed', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uid', type=int, required=True)
    parser.add_argument('--display', help='Open tracked test app windows on this host X11/XWayland display')
    arguments = parser.parse_args()
    if os.geteuid() != 0 or arguments.uid <= 0:
        parser.error('Requires administrator and a non-root desktop UID')
    verify(arguments.uid, arguments.display)
