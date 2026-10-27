"""In-memory test runtime, never selected for the production System D-Bus service."""

from cyberlab.lab.environment import workspace
from cyberlab.runtime import RuntimeFailure
from cyberlab.workspace import Entry


class MemoryRuntime:
    name = "memory-test"

    def __init__(self):
        self.active = set()
        self.files = {}
        self.imported = {}

    def start(self, session, workspaces=None):
        self.active.add(session.id)
        if workspaces:
            from cyberlab.workspace import read_archive
            self.files[session.id] = {
                node.id: {entry.path: entry.data for entry in read_archive(workspaces[node.id], unsafe=True)}
                for node in session.lab.nodes if node.id in workspaces
            }
            for node in session.lab.nodes:
                if node.id not in self.files[session.id]:
                    self.files[session.id][node.id] = {entry.path: entry.data for entry in node.seed}
        else:
            self.files[session.id] = {
                node.id: {entry.path: entry.data for entry in node.seed}
                for node in session.lab.nodes
            }
        self.imported[session.id] = {}

    def import_file(self, session, record, data):
        self.imported[session.id][record.id] = (record.node, record.path, data)
        node = next(node for node in session.lab.nodes if node.id == record.node)
        self.files[session.id][record.node][record.path.removeprefix(workspace(node) + "/")] = data

    def workspace(self, session, node):
        return tuple(Entry(path, "directory" if data is None else "file", data, 0o700 if data is None else 0o600)
                     for path, data in self.files[session.id][node.id].items())

    def import_workspace(self, session, node, name, entries):
        existing = self.files[session.id][node.id]
        if any(path == name or path.startswith(name + "/") for path in existing):
            raise RuntimeFailure("Import destination already exists")
        existing[name] = None
        existing.update({f"{name}/{entry.path}": entry.data for entry in entries})

    def remove(self, session_id):
        self.active.discard(session_id)
        self.files.pop(session_id, None)
        self.imported.pop(session_id, None)

    def running(self, session):
        return session.id in self.active

    def cleanup(self):
        self.active.clear()
        self.files.clear()
        self.imported.clear()

    def open_terminal(self, session, node_id):
        return MemoryTerminal()

class MemoryTerminal:
    def __init__(self):
        self.output = bytearray(b"MEMORY TEST terminal (not a shell)\r\n")
        self.ended = False

    def read(self, limit):
        data = bytes(self.output[:limit])
        del self.output[:limit]
        return data, self.ended and not self.output

    def write(self, data):
        count = min(len(data), 4096 - len(self.output))
        self.output.extend(data[:count])
        if b"\x04" in data[:count]:
            self.ended = True
        return count

    def resize(self, rows, columns):
        self.size = (rows, columns)

    def close(self):
        self.ended = True

    def exited(self):
        return self.ended
