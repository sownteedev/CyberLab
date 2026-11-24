"""Prepare owner-bound runtime context over the existing daemon connection."""

import asyncio
from contextlib import suppress
import json
import os
import sys

from cyberlab.host_display import helper
from cyberlab import x11
from .gui_environment import inspect_environment


async def prepare(bus, request):
    if not x11.NATIVE_X11_ENABLED:
        raise ValueError(x11.NATIVE_X11_DISABLED_REASON)
    report = await asyncio.to_thread(inspect_environment)
    credential = None
    phase = 'host-authorization'
    try:
        if report['backend'] == 'native-x11' and report['ready']:
            credential = await asyncio.to_thread(helper, {'display': os.environ['DISPLAY'], 'operation': 'generate'})
            phase = 'daemon-context'
            payload = {**credential, 'display': os.environ['DISPLAY'], 'login': report['login']}
            return await request(bus, 'PrepareDesktopContext', [json.dumps(payload)])
    except Exception:
        if credential:
            with suppress(Exception):
                await asyncio.to_thread(helper, {**credential, 'display': os.environ['DISPLAY'], 'operation': 'revoke'})
        report['fallback_reason'] = f'Native X11 authorization failed [{phase}]; using Xpra when available'
    reason = report.get('fallback_reason', '')
    if reason:
        print(reason, file=sys.stderr)
    payload = {'fallback': reason, 'requested_backend': report.get('preferred', 'auto')}
    return await request(bus, 'PrepareDesktopContext', [json.dumps(payload)])


async def lifecycle(bus, request, arguments, parameters):
    token = None
    if not arguments.test_session_bus and x11.NATIVE_X11_ENABLED:
        capabilities = await request(bus, 'GetCapabilities', [])
        if 'native-x11' in capabilities:
            token = await prepare(bus, request)
    try:
        if arguments.command == 'start':
            return await request(bus, 'StartLabWithDesktop' if token else 'StartLabWithParameters',
                                 [arguments.id, parameters, token] if token else [arguments.id, parameters])
        operation = 'ResumeSession' if arguments.command == 'resume' else 'ResetSession'
        return await request(bus, operation + 'WithDesktop' if token else operation,
                             [arguments.id, token] if token else [arguments.id])
    finally:
        if token:
            with suppress(Exception):
                await request(bus, 'ReleaseDesktopContext', [token])
