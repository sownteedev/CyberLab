"""Memory-only edit grants and stdin-only credential transport."""
from contextlib import contextmanager
from contextvars import ContextVar
import io
import json
import sys

_token = ContextVar('edit_token', default='')
MAX_CONTEXT = 40 * 1024 * 1024


def token():
    return _token.get()


def read_payload(limit):
    if sys.stdin.isatty():
        raise ValueError('Editing credentials require JSON stdin')
    data = sys.stdin.buffer.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Editing input exceeds the size limit')
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeError):
        raise ValueError('Invalid editing JSON input') from None
    if not isinstance(payload, dict):
        raise ValueError('Editing input must be a JSON object')
    return payload


@contextmanager
def context(enabled):
    if not enabled:
        yield
        return
    payload = read_payload(MAX_CONTEXT)
    if set(payload) != {'token', 'input'} or not all(isinstance(payload[key], str) for key in payload):
        raise ValueError('Editing context requires token and input strings')
    if not payload['token'] or len(payload['token']) > 4096:
        raise ValueError('Invalid editing context token')
    previous = sys.stdin
    replacement = io.TextIOWrapper(io.BytesIO(payload['input'].encode('utf-8')), encoding='utf-8')
    handle = _token.set(payload['token'])
    try:
        sys.stdin = replacement
        yield
    finally:
        sys.stdin = previous
        _token.reset(handle)
        replacement.close()


def add_parser(commands):
    parser = commands.add_parser('edit-access', help='Manage editing protection using JSON stdin only')
    parser.add_argument('edit_action', choices=('unlock', 'protect', 'revoke'))


def prepare(arguments):
    payload = read_payload(16384)
    fields = {'unlock': ('kind', 'id', 'password'),
              'protect': ('kind', 'id', 'currentPassword', 'newPassword'),
              'revoke': ('token',)}[arguments.edit_action]
    if set(payload) != set(fields) or not all(isinstance(payload[key], str) for key in fields):
        raise ValueError('Invalid editing credential fields')
    if arguments.edit_action != 'revoke' and (payload['kind'] not in ('lab', 'draft') or not payload['id']):
        raise ValueError('Invalid editing resource')
    return [payload[key] for key in fields]


async def run(bus, request, arguments, prepared):
    method = {'unlock': 'UnlockEditing', 'protect': 'SetEditPassword', 'revoke': 'RevokeEditing'}[arguments.edit_action]
    result = await request(bus, method, prepared)
    return result if arguments.edit_action == 'revoke' else json.loads(result)
