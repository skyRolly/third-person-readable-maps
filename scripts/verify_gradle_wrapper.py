#!/usr/bin/env python3
"""Validate a canonical Wrapper configuration without executing the Wrapper.

The accepted subset is deliberately narrower than java.util.Properties: ASCII
key=value lines only, with one known escape in distributionUrl. This makes
the checked values identical to the values consumed by Java's properties parser.
"""
import argparse
import hashlib
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://services.gradle.org/distributions/'
URL = re.compile(r'https\\://services\.gradle\.org/distributions/gradle-([0-9]+\.[0-9]+\.[0-9]+)-bin\.zip')
DIGEST = re.compile(r'[0-9a-f]{64}')
FIXED = {'distributionBase': 'GRADLE_USER_HOME', 'distributionPath': 'wrapper/dists',
         'zipStoreBase': 'GRADLE_USER_HOME', 'zipStorePath': 'wrapper/dists',
         'validateDistributionUrl': 'true'}
NUMERIC = {'networkTimeout', 'retries', 'retryBackOffMs'}
REQUIRED = {'distributionBase', 'distributionPath', 'distributionSha256Sum',
            'distributionUrl', 'zipStoreBase', 'zipStorePath'}


def canonical_properties(raw):
    # Java Properties.load(InputStream) uses ISO-8859-1. The ASCII subset has
    # identical code points and intentionally excludes continuations, unicode
    # escapes, whitespace/separator variants and unknown Wrapper options.
    text = raw.decode('ascii')
    if any(ord(c) < 32 and c not in '\r\n' for c in text) or '\x7f' in text:
        raise ValueError('unsupported control character in wrapper properties')
    properties = {}
    for line in text.splitlines():
        if not line or line.startswith(('#', '!')):
            continue
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*=[!-~]+', line):
            raise ValueError('noncanonical wrapper property')
        key, value = line.split('=', 1)
        if key in properties:
            raise ValueError('duplicate wrapper property: ' + key)
        if key in FIXED:
            if value != FIXED[key]:
                raise ValueError('unsupported wrapper property value: ' + key)
        elif key in NUMERIC:
            if not re.fullmatch(r'[0-9]{1,9}', value):
                raise ValueError('invalid numeric wrapper property: ' + key)
        elif key == 'distributionUrl':
            if not URL.fullmatch(value):
                raise ValueError('unsupported or untrusted Gradle distribution URL')
        elif key == 'distributionSha256Sum':
            if not DIGEST.fullmatch(value):
                raise ValueError('invalid distribution checksum')
        else:
            raise ValueError('unsupported wrapper property: ' + key)
        properties[key] = value
    if not REQUIRED <= properties.keys():
        raise ValueError('missing required wrapper properties: ' + ', '.join(sorted(REQUIRED - properties.keys())))
    return properties


class GradleChecksumRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if (new.scheme != 'https' or new.hostname not in ('services.gradle.org', 'downloads.gradle.org') or
                new.username is not None or new.password is not None or new.port not in (None, 443) or
                new.path != old.path or new.query or new.fragment):
            raise ValueError('untrusted checksum redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def published(url):
    with build_opener(GradleChecksumRedirect()).open(url, timeout=30) as response:
        value = response.read(256).decode('ascii').strip().lower()
    if not DIGEST.fullmatch(value):
        raise ValueError('invalid published SHA-256')
    return value


def verify(root, fetch=published):
    properties = canonical_properties((root/'gradle/wrapper/gradle-wrapper.properties').read_bytes())
    version = URL.fullmatch(properties['distributionUrl']).group(1)
    expected_jar = fetch(BASE + 'gradle-' + version + '-wrapper.jar.sha256')
    expected_distribution = fetch(BASE + 'gradle-' + version + '-bin.zip.sha256')
    if not DIGEST.fullmatch(expected_jar) or not DIGEST.fullmatch(expected_distribution):
        raise ValueError('invalid published SHA-256')
    actual_jar = hashlib.sha256((root/'gradle/wrapper/gradle-wrapper.jar').read_bytes()).hexdigest()
    if actual_jar != expected_jar:
        raise ValueError('Gradle wrapper JAR checksum mismatch')
    if properties['distributionSha256Sum'] != expected_distribution:
        raise ValueError('Gradle distribution checksum does not match the published value')
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='source tree containing gradle/wrapper')
    args = parser.parse_args()
    try:
        print('Verified Gradle ' + verify(args.root) + ' wrapper checksums')
    except (OSError, ValueError, UnicodeError) as exc:
        print('Gradle wrapper verification failed: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
