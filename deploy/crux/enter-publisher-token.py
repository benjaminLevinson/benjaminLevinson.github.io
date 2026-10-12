#!/usr/bin/env python3
"""Run manually in a private SSH terminal; never invoke through an assistant.

The user creates, enters, and stores the credential. Nothing is sent over the
network by this helper, and no credential is placed in argv or shell history.
"""
import getpass
import os
from pathlib import Path
import stat
import sys
import warnings


def main():
    if len(sys.argv) != 2 or not sys.stdin.isatty():
        raise ValueError('Use a private interactive terminal and one destination path')
    destination = Path(sys.argv[1])
    if not destination.is_absolute():
        raise ValueError('Destination must be absolute')
    os.umask(0o077)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = destination.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Secret directory must be owned by this user with mode 0700')
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination already exists; no credential was changed')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        token = getpass.getpass('Paste the approved fine-grained GitHub token (hidden): ')
    if not token.startswith('github_pat_') or any(c.isspace() for c in token):
        raise ValueError('Expected a fine-grained token without whitespace')
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(token + '\n')
        output.flush()
        os.fsync(output.fileno())
    del token
    print('Credential stored privately. Its permissions and expiry still require verification in GitHub settings.')


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print('Credential setup stopped: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
