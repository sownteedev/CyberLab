#!/usr/bin/env python3
"""Real Studio -> CLI -> private D-Bus authoring; no Docker or production data."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import argparse
import asyncio
import json
import os
import selectors
import shutil
import signal
import subprocess
import tempfile
import time


async def serve(root):
    from dbus_next import BusType, NameFlag
    from dbus_next.aio import MessageBus
    from cyberlab.authoring import Authoring
    from cyberlab.lab.workstation import UBUNTU_IMAGE
    from cyberlab.policy import RuntimePolicy
    from cyberlab.service import Engine
    from cyberlab.session.persistence import PracticeStore
    from cyberlab_ipc import BUS_NAME
    from cyberlabd.server import Server
    from cyberlabd.testing import MemoryRuntime

    policy = RuntimePolicy(frozenset({UBUNTU_IMAGE}), workstation_images=frozenset({UBUNTU_IMAGE}))
    catalog = root / 'catalog'
    catalog.mkdir(exist_ok=True)
    engine = Engine(catalog, policy, MemoryRuntime(), PracticeStore(root / 'practice.sqlite3'))
    authoring = Authoring(root / 'drafts.sqlite3', catalog, policy)
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
    server = Server(bus, engine, frozenset({os.getuid()}), authoring)
    bus.add_message_handler(server.handle)
    await asyncio.Event().wait()


QML = '''//@ pragma UseQApplication
import QtQuick
import QtQuick.Controls.Basic
import Quickshell
import QtTest
import STUDIO as Studio
ShellRoot {
    Studio.Backend {
        id: backend
        prefix: SOURCE_PREFIX.concat(["cyberlab_cli.main", "--test-session-bus"])
    }
    ApplicationWindow {
        id: window
        visible: true
        width: 1440; height: 1000
        title: "CyberLab isolated setup acceptance"
        palette: Studio.Theme.controlPalette
        Studio.DraftEditor { id: editor; anchors.fill: parent; backend: backend }
        TestCase {
            id: checks
            name: "NativeMachineSetupWorkflow"
            when: window.visible
            function control(name) {
                const item = findChild(editor, name) || findChild(window, name);
                verify(item !== null, "Missing control " + name + " section=" + editor.service.section + " draft=" + !!editor.service.draft);
                return item;
            }
            function reveal(item) {
                let parent = item.parent;
                while (parent) {
                    if (parent.contentY !== undefined && parent.contentHeight !== undefined && parent.contentItem) {
                        const position = item.mapToItem(parent.contentItem, 0, 0);
                        parent.contentY = Math.max(0, Math.min(parent.contentHeight - parent.height, position.y - 24));
                    }
                    parent = parent.parent;
                }
                wait(80);
            }
            function click(name) {
                const item = control(name);
                reveal(item);
                verify(item.enabled, "Disabled control " + name);
                item.clicked();
                wait(80);
            }
            function fill(name, value) {
                const item = control(name);
                reveal(item);
                item.forceActiveFocus();
                item.text = value;
            }
            function idle() { tryVerify(() => !backend.busy, 15000); compare(backend.error, ""); }
            function test_author_create_save_reopen() {
                try { runWorkflow(); }
                catch (error) { console.error("WORKFLOW_FAILURE: " + error + " " + error.stack); throw error; }
            }
            function runWorkflow() {
                verify(waitForPolish(window));
                console.log("WORKFLOW: loading capabilities");
                let ready = false;
                backend.request(["info"], (result, error) => { if (!error) { backend.capabilities = result.capabilities; ready = true; } });
                tryVerify(() => ready, 15000);
                editor.service.refresh();
                tryVerify(() => !!editor.service.policy && !backend.busy, 15000);
                console.log("WORKFLOW: creating through controls");
                fill("newDraftTitle", "Linux machine setup acceptance");
                fill("newDraftId", "setup-acceptance");
                // TopicPicker opens a separate Popup window in Quickshell; commit the
                // selected chip through the same signal after the visible control is opened.
                click("newDraftTopics");
                const topics = control("newDraftTopics");
                topics.edited(["linux"]);
                topics.dialog.close();
                control("newDraftDifficulty").currentIndex = 1;
                wait(80);
                click("createDraftButton");
                tryVerify(() => !!editor.service.draft, 15000);
                idle();
                console.log("WORKFLOW: section click"); editor.service.section = 1; wait(120);
                editor.service.addMachine(); wait(120);
                compare(editor.service.document.nodes.length, 1);
                // The account panel has its own tested user-like QML workflow;
                // here the real DraftService mutators feed the same serialized draft.
                editor.service.accountChange(0, "addUser", "frank");
                editor.service.accountChange(0, "addUser", "mary");
                editor.service.accountChange(0, "addGroup", "bakers");
                editor.service.accountChange(0, "groups", "frank", ["bakers"]);
                compare(editor.service.document.nodes[0].setup.users.length, 2);
                editor.service.addMachine();
                compare(editor.service.document.nodes.length, 2);
                compare(editor.service.document.networks.length, 1);
                const nodeId = editor.service.document.nodes[0].id;
                editor.service.files.create(nodeId, "answer.txt", false);
                editor.service.files.edit(nodeId, "answer.txt", "wrong");
                editor.service.addNestedEntry("assessment", "results", {id: "answer", node: nodeId, path: "answer.txt", operator: "equals", expected: "correct"}, 32);
                editor.service.addNestedEntry("assessment", "goals", {id: "done", type: "boolean", expression: "answer"}, 32);
                editor.service.changePath(["settings", "checkwork"], true);
                editor.service.addQuizGroup({id: "intro", pre_start: true, items: [
                    {id: "first", type: "choice", question: "Choose", options: ["Yes", "No"], answer: 0}]}, 8);
                compare(editor.service.localError, "");
                click("saveDraftButton");
                idle();
                const draftId = editor.service.draft.id;
                const revision = editor.service.draft.revision;
                const users = editor.service.document.nodes[0].setup.users;
                compare(users.length, 2);
                compare(users[0].name, "frank");
                verify(users[0].groups.includes("bakers"));
                verify(!editor.service.dirty);
                const validation = request(["draft", "check", draftId, "--revision", String(revision)]);
                if (!validation.valid) console.error("WORKFLOW_VALIDATION: " + JSON.stringify(validation));
                verify(validation.valid);
                let exported = false;
                backend.request(["export-draft", draftId, ARCHIVE, "--revision", String(revision)],
                                (result, error) => { exported = !error; });
                tryVerify(() => exported && !backend.busy, 15000);
                let imported = false;
                backend.request(["import-lab", ARCHIVE, "--as", "setup-imported", "--title", "Imported setup"],
                                (result, error) => { imported = !error && !!result; });
                tryVerify(() => imported && !backend.busy, 15000);
                editor.service.openDraft(draftId, true);
                idle();
                compare(editor.service.document.nodes[0].setup.users.length, 2);
                compare(editor.service.document.nodes[0].setup.users[0].groups[0], "bakers");
                compare(editor.service.document.nodes.length, 2);
                compare(editor.service.document.metadata.difficulty, "easy");
                compare(editor.service.document.quizzes[0].items.length, 1);
                compare(editor.service.document.assessment.goals[0].expression, "answer");
                const quiz = request(["lab-quiz", "setup-imported"]);
                const attempt = request(["lab-quiz", "setup-imported", "--digest", quiz.lab_digest, "--answer", "first=1"]);
                verify(!attempt.passed);
                const session = request(["start", "setup-imported", "--no-terminals"]);
                compare(session.state, "RUNNING");
                const report = request(["checkwork", session.id]);
                compare(report.status, "FAIL");
                const saveFailure = request(["save", session.id], true);
                verify(saveFailure.includes("Ubuntu"));
                const retained = request(["status", session.id]);
                compare(retained.state, "RUNNING");
                verify(!retained.saved);
                compare(request(["checkwork", session.id]).status, "FAIL");
                request(["stop", session.id]);
                console.log("CYBERLAB_MACHINE_SETUP_UI_DBUS_PASS");
            }
            function request(argv, expectFailure) {
                let finished = false;
                let value = null;
                let failure = "";
                backend.request(argv, (result, error) => { value = result; failure = error; finished = true; });
                tryVerify(() => finished && !backend.busy, 15000);
                if (expectFailure) { verify(!!failure, argv.join(" ")); return failure; }
                compare(failure, "", argv.join(" "));
                return value;
            }
        }
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', type=Path)
    parser.add_argument('--visible', action='store_true')
    parser.add_argument('--artifacts', type=Path, default=Path('/tmp/cyberlab-machine-setup-artifacts'))
    arguments = parser.parse_args()
    if arguments.serve:
        asyncio.run(serve(arguments.serve))
        return 0
    repository = Path(__file__).resolve().parents[3]
    bootstrap = ("import runpy,sys; sys.path[:0]="
                 + repr([str(repository / name) for name in ('cli', 'engine', 'daemon', '.')])
                 + "; from tools.tests.unit import check_workstations; sys.argv=sys.argv[1:]; runpy.run_module(sys.argv[0],run_name='__main__')")
    source_prefix = [sys.executable, '-I', '-c', bootstrap]
    arguments.artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cyberlab-setup-workflow-') as directory:
        root = Path(directory)
        processes = []
        try:
            bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            processes.append(bus)
            with selectors.DefaultSelector() as selector:
                selector.register(bus.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=5):
                    raise RuntimeError('Private D-Bus did not start')
            environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip())
            for name in ('home', 'config', 'cache', 'data', 'runtime'):
                (root / name).mkdir(mode=0o700)
            environment.update(HOME=str(root / 'home'), XDG_CONFIG_HOME=str(root / 'config'),
                               XDG_CONFIG_DIRS=str(root / 'config'), XDG_CACHE_HOME=str(root / 'cache'),
                               XDG_DATA_HOME=str(root / 'data'), XDG_RUNTIME_DIR=str(root / 'runtime'))
            if not arguments.visible:
                environment.pop('WAYLAND_DISPLAY', None)
                environment.pop('DISPLAY', None)
                environment.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
            with (arguments.artifacts / 'workflow-daemon.log').open('w') as log:
                daemon = subprocess.Popen([*source_prefix, 'tools.tests.ui.check_machine_setup_workflow', '--serve', str(root)],
                                          env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(daemon)
                for attempt in range(40):
                    result = subprocess.run([*source_prefix, 'cyberlab_cli.main', '--test-session-bus', 'info'],
                                            env=environment, capture_output=True, timeout=10)
                    if result.returncode == 0:
                        break
                    if daemon.poll() is not None:
                        raise RuntimeError((arguments.artifacts / 'workflow-daemon.log').read_text())
                    time.sleep(0.1)
                else:
                    raise RuntimeError('Private daemon did not become ready')
                studio = root / 'studio'
                shutil.copytree(repository / 'ui/studio', studio)
                source = QML.replace('STUDIO', '"."')
                source = source.replace('SOURCE_PREFIX', json.dumps(source_prefix)).replace('ARCHIVE', json.dumps(str(root / 'fixture.cyberlab')))
                (studio / 'shell.qml').write_text(source)
                process = subprocess.Popen(['/usr/bin/quickshell', '-p', str(studio / 'shell.qml')], env=environment,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
                processes.append(process)
                try:
                    output, _ = process.communicate(timeout=120)
                except subprocess.TimeoutExpired as error:
                    output = error.output or ''
                    if isinstance(output, bytes):
                        output = output.decode(errors='replace')
                    (arguments.artifacts / 'workflow-ui.log').write_text(output)
                    raise
                (arguments.artifacts / 'workflow-ui.log').write_text(output)
                print(output)
                return process.returncode or int('CYBERLAB_MACHINE_SETUP_UI_DBUS_PASS' not in output)
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()


if __name__ == '__main__':
    raise SystemExit(main())
