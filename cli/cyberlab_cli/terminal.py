import asyncio
from contextlib import suppress
import os
import select
import signal
import sys
import termios
import tty

def terminal_size(descriptor):
    size = os.get_terminal_size(descriptor)
    return [max(1, min(size.lines, 1000)), max(1, min(size.columns, 1000))]

async def interact(bus, request, session_id, node_id, slot=0, *, window_token=None, window_title="", test_session_bus=False):
    if window_token is not None:
        from .window_registry import decode_title

        window_title = decode_title(window_title)
    input_fd, output_fd = sys.stdin.fileno(), sys.stdout.fileno()
    if not os.isatty(input_fd) or not os.isatty(output_fd):
        raise RuntimeError("terminal requires an interactive TTY for stdin and stdout")
    size = terminal_size(input_fd)
    previous = termios.tcgetattr(input_fd)
    handle = await request(bus, "OpenTerminalSlot", [session_id, node_id, slot, *size]) if slot else await request(bus, "OpenTerminal", [session_id, node_id, *size])
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    handlers = {}
    try:
        from .desktop import attach_prepared

        for signum in (signal.SIGTERM, signal.SIGHUP):
            handlers[signum] = signal.getsignal(signum)
            loop.add_signal_handler(signum, task.cancel)
        await attach_prepared(bus, request, session_id, node_id, test_session_bus)
        if window_token is not None:
            from .window_registry import register_attachment

            register_attachment(session_id, node_id, slot, window_token, window_title, test_session_bus)
            safe_title = "".join(character for character in window_title if character.isprintable())[:128]
            os.write(output_fd, f"\033]0;{safe_title}\007".encode("utf-8"))
        print("Connected. Ctrl+] detaches; exit ends the shell.", file=sys.stderr, flush=True)
        tty.setraw(input_fd)
        pending = b""
        while True:
            output, ended = await request(bus, "ReadTerminal", [handle])
            while output:
                count = os.write(output_fd, output)
                output = output[count:]
            if ended:
                break
            current_size = terminal_size(input_fd)
            if current_size != size:
                await request(bus, "ResizeTerminal", [handle, *current_size])
                size = current_size
            if not pending and select.select([input_fd], [], [], 0)[0]:
                pending = os.read(input_fd, 4096)
                if not pending or b"\x1d" in pending:
                    break
            if pending:
                accepted = await request(bus, "WriteTerminal", [handle, pending])
                if not 0 <= accepted <= len(pending):
                    raise RuntimeError("Invalid terminal write acknowledgement")
                pending = pending[accepted:]
            await asyncio.sleep(0.02)
    finally:
        try:
            termios.tcsetattr(input_fd, termios.TCSANOW, previous)
        finally:
            for signum, handler in handlers.items():
                loop.remove_signal_handler(signum)
                signal.signal(signum, handler)
            with suppress(Exception):
                await asyncio.wait_for(request(bus, "CloseTerminal", [handle]), timeout=2)
            if window_token is not None:
                from .window_registry import unregister_attachment

                with suppress(OSError, ValueError):
                    unregister_attachment(session_id, window_token, test_session_bus)
