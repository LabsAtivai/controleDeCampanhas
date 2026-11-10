"""Check current source files without printing matched secret values."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [re.compile(rb'SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}'),
            re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]


def main():
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=ROOT, capture_output=True, check=True)
    failures = []
    for name in result.stdout.decode('utf-8').split('\0'):
        if not name:
            continue
        path = ROOT / name
        if path.is_file():
            content = path.read_bytes()
            if any(pattern.search(content) for pattern in PATTERNS):
                failures.append(name)
    if failures:
        print('Possíveis segredos encontrados nos arquivos: ' + ', '.join(failures))
        return 1
    print('Nenhum segredo dos padrões verificados encontrado no código atual.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
