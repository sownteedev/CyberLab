"""Read-only APT source preflight; APT still verifies signatures before installing."""

import argparse
import gzip
import io
import re
import urllib.request
import zlib

MAX_COMPRESSED = 4 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
UBUNTU = 'https://ppa.launchpadcontent.net/avengemedia/danklinux/ubuntu'
DEBIAN = 'https://downloadcontent.opensuse.org/repositories/home:/AvengeMedia:/danklinux/Debian_13'
GUIDE = 'https://quickshell.org/docs/v0.3.2/guide/install-setup/'


class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        if not url.startswith('https://'):
            raise ValueError('Repository redirect requires HTTPS')
        return super().redirect_request(request, response, code, message, headers, url)


def index_url(base, suite, architecture):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', architecture):
        raise ValueError('Invalid package architecture')
    if base == UBUNTU and re.fullmatch(r'[a-z]+', suite):
        return f'{base}/dists/{suite}/main/binary-{architecture}/Packages.gz'
    if base == DEBIAN and suite == '/':
        return f'{base}/Packages.gz'
    raise ValueError('Unreviewed repository or invalid suite')


def decode_index(data):
    if len(data) > MAX_COMPRESSED:
        raise ValueError('Package index download exceeds its limit')
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as source:
        expanded = source.read(MAX_EXPANDED + 1)
    if len(expanded) > MAX_EXPANDED:
        raise ValueError('Package index expansion exceeds its limit')
    return expanded.decode('utf-8')


def select_package(text, architecture):
    for block in text.replace('\r\n', '\n').split('\n\n'):
        fields = {}
        for line in block.splitlines():
            if not line or line[0].isspace():
                continue
            key, separator, value = line.partition(':')
            if not separator or key in fields:
                raise ValueError('Malformed or duplicate package field')
            fields[key] = value.strip()
        if fields.get('Package') != 'quickshell' or fields.get('Architecture') not in (architecture, 'all'):
            continue
        version = fields.get('Version', '')
        match = re.fullmatch(r'(?:\d+:)?(\d+)\.(\d+)\.(\d+)([a-zA-Z0-9.+~\-]*)', version)
        if match:
            release = tuple(int(value) for value in match.groups()[:3])
            if release > (0, 3, 1) or (release == (0, 3, 1) and '~' not in match.group(4)):
                return version
    raise ValueError('Không có gói quickshell >= 0.3.1 cho nền/kiến trúc này trong nguồn đã chọn')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--suite', required=True)
    parser.add_argument('--architecture', required=True)
    args = parser.parse_args()
    try:
        url = index_url(args.base, args.suite, args.architecture)
        request = urllib.request.Request(url, headers={'User-Agent': 'CyberLab-installer'})
        with urllib.request.build_opener(HttpsRedirect()).open(request, timeout=30) as response:
            data = response.read(MAX_COMPRESSED + 1)
        version = select_package(decode_index(data), args.architecture)
    except (OSError, ValueError, EOFError, zlib.error) as error:
        raise SystemExit(f'Không xác minh được nguồn Quickshell ({args.suite}/{args.architecture}): {error}. '
                         f'Chưa thêm nguồn hoặc cài gói. Hướng dẫn upstream: {GUIDE}') from None
    print(f'Nguồn có Quickshell {version} ({args.suite}/{args.architecture}). '
          'APT vẫn phải xác minh chữ ký và giải dependency; đây chưa phải xác nhận cài thành công.')


if __name__ == '__main__':
    main()
