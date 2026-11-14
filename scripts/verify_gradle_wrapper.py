#!/usr/bin/env python3
"""Compare the wrapper JAR and pinned distribution checksum with Gradle's published values."""
import hashlib
from pathlib import Path
import re
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://services.gradle.org/distributions/'


def published(url):
    with urlopen(url, timeout=30) as response:
        value = response.read().decode('ascii').strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('invalid published SHA-256')
    return value


def verify(root, fetch=published):
    properties = {}
    for line in (root/'gradle/wrapper/gradle-wrapper.properties').read_text().splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        key, value = line.split('=', 1)
        if key in properties:
            raise ValueError('duplicate wrapper property: ' + key)
        properties[key] = value
    url = properties.get('distributionUrl', '').replace('\\:', ':')
    match = re.fullmatch(re.escape(BASE) + r'gradle-([0-9]+\.[0-9]+\.[0-9]+)-bin\.zip', url)
    if not match:
        raise ValueError('unsupported or untrusted Gradle distribution URL')
    version = match.group(1)
    expected_jar = fetch(BASE + 'gradle-' + version + '-wrapper.jar.sha256')
    actual_jar = hashlib.sha256((root/'gradle/wrapper/gradle-wrapper.jar').read_bytes()).hexdigest()
    if actual_jar != expected_jar:
        raise ValueError('Gradle wrapper JAR checksum mismatch')
    if properties.get('distributionSha256Sum', '').lower() != fetch(url + '.sha256'):
        raise ValueError('Gradle distribution checksum does not match the published value')
    return version


def main():
    try:
        print('Verified Gradle ' + verify(ROOT) + ' wrapper checksums')
    except (OSError, ValueError, UnicodeError) as exc:
        print('Gradle wrapper verification failed: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
