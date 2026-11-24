"""Isolated edit access client checks; no daemon or catalog access."""
import argparse
import asyncio
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ('cli', 'daemon', 'engine')]
from cyberlab_cli import edit_access


class EditAccessChecks(unittest.TestCase):
    def test_unlock_stdin_only(self):
        parser = argparse.ArgumentParser()
        edit_access.add_parser(parser.add_subparsers(dest='command'))
        args = parser.parse_args(['edit-access', 'unlock'])
        payload = {'kind': 'draft', 'id': 'fixture', 'password': 'private'}
        with patch('sys.stdin', io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode()))):
            prepared = edit_access.prepare(args)
        request = AsyncMock(return_value='{"token":"grant","edit_protected":true}')
        result = asyncio.run(edit_access.run(None, request, args, prepared))
        request.assert_awaited_once_with(None, 'UnlockEditing', ['draft', 'fixture', 'private'])
        self.assertEqual(result['token'], 'grant')
        with self.assertRaises(SystemExit):
            parser.parse_args(['edit-access', 'unlock', '--password', 'private'])

    def test_context_restores_binary_stdin_and_clears_token(self):
        original = io.TextIOWrapper(io.BytesIO(json.dumps({'token': 'grant', 'input': 'retained\ninput'}).encode()))
        with patch('sys.stdin', original):
            with edit_access.context(True):
                self.assertEqual(edit_access.token(), 'grant')
                self.assertEqual(sys.stdin.buffer.read(), b'retained\ninput')
            self.assertIs(sys.stdin, original)
            self.assertEqual(edit_access.token(), '')

    def test_invalid_payload_does_not_echo_secrets(self):
        for payload in ({'token': 'private'}, {'token': [], 'input': 'private'}):
            with patch('sys.stdin', io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode()))):
                with self.assertRaises(ValueError) as caught:
                    with edit_access.context(True):
                        pass
            self.assertNotIn('private', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
