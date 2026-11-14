"""Small HTTPS-only curl-compatible adapter for the pinned build scripts."""
from pathlib import Path
import os
import sys
import time
import urllib.error
import urllib.request


def options(arguments):
    output, url, resume, limit, retries, timeout = None, None, False, None, 0, 90
    i = 0
    while i < len(arguments):
        value = arguments[i]
        if value in ('-o', '--output', '--continue-at', '-C', '--max-filesize', '--retry',
                     '--retry-delay', '--connect-timeout', '--proto', '--proto-redir'):
            i += 1
            if i == len(arguments):
                raise ValueError('Missing HTTPS download option value')
            parameter = arguments[i]
            if value in ('-o', '--output'):
                output = Path(parameter)
            elif value in ('--continue-at', '-C'):
                if parameter != '-':
                    raise ValueError('Only verified automatic download resume is supported')
                resume = True
            elif value == '--max-filesize':
                limit = int(parameter)
            elif value == '--retry':
                retries = min(5, max(0, int(parameter)))
            elif value == '--connect-timeout':
                timeout = min(120, max(5, int(parameter)))
            elif value in ('--proto', '--proto-redir') and parameter != '=https':
                raise ValueError('Game setup downloads require HTTPS')
        elif value.startswith('-'):
            if value not in ('--fail', '--location', '--silent', '--show-error') and not (
                    value.startswith('-') and not value.startswith('--') and set(value[1:]) <= set('fLsS')):
                raise ValueError('Unsupported HTTPS download option: ' + value)
        elif url is None:
            url = value
        else:
            raise ValueError('One download is supported per command')
        i += 1
    if not url or not url.startswith('https://') or output is None:
        raise ValueError('A pinned HTTPS URL and output file are required')
    return dict(url=url, output=output, resume=resume, limit=limit, retries=retries, timeout=timeout)


def download(url, output, resume=False, limit=None, retries=0, timeout=90):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries + 1):
        try:
            offset = output.stat().st_size if resume and output.exists() else 0
            headers = {'User-Agent': 'SuperMelee64-Setup'}
            if offset:
                headers['Range'] = 'bytes=' + str(offset) + '-'
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as source:
                if not source.url.startswith('https://'):
                    raise ValueError('Download redirected away from HTTPS')
                append = offset and source.status == 206
                size = offset if append else 0
                with output.open('ab' if append else 'wb') as target:
                    while block := source.read(1024 * 1024):
                        cancel = os.environ.get('SMB_SETUP_CANCEL')
                        if cancel and Path(cancel).exists():
                            return 130
                        size += len(block)
                        if limit is not None and size > limit:
                            raise ValueError('Download exceeded its pinned size')
                        target.write(block)
            return 0
        except urllib.error.HTTPError as error:
            if error.code == 416:
                return 33
            if attempt == retries:
                raise
        except (OSError, urllib.error.URLError):
            if attempt == retries:
                raise
        time.sleep(1)
    return 1


def main():
    if sys.argv[1:] == ['--version']:
        print('Super Melee 64 private HTTPS download adapter')
        return 0
    try:
        return download(**options(sys.argv[1:]))
    except (ValueError, OSError, urllib.error.URLError) as error:
        print('HTTPS download failed: ' + str(error), file=sys.stderr)
        return 22


if __name__ == '__main__':
    raise SystemExit(main())
