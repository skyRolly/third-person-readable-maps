"""Exercise candidate JAR identity and Mixin registration gates."""
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import warnings
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import game_linkage
import verify_supported_apis as verifier
from test_linkage_invalid_inputs import new_fixture


def inputs():
    metadata = json.loads((ROOT / 'src/main/resources/fabric.mod.json').read_text())
    properties = dict(line.split('=', 1) for line in (ROOT / 'gradle.properties').read_text().splitlines()
                      if '=' in line and not line.lstrip().startswith('#'))
    def expand(value):
        if isinstance(value, str):
            return re.sub(r'\$\{([^}]+)\}', lambda match: properties[match.group(1)], value)
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        return value
    metadata['depends']['minecraft'] = expand(metadata['depends']['minecraft'])
    return metadata, json.loads((ROOT / 'src/main/resources/thirdpersonreadablemaps.mixins.json').read_text())


def candidate(kind, config):
    metadata, _ = inputs()
    data = io.BytesIO()
    with warnings.catch_warnings(), ZipFile(data, 'w') as jar:
        warnings.simplefilter('ignore', UserWarning)
        jar.writestr('fabric.mod.json', json.dumps(metadata))
        jar.writestr('thirdpersonreadablemaps.mixins.json', json.dumps(config))
        name = 'fixture/Renamed.class' if kind == 'wrong-name' else 'fixture/Caller.class'
        jar.writestr(name, new_fixture(4))
        if kind == 'duplicate':
            jar.writestr(name, new_fixture(4))
    return data.getvalue()


class CandidateJarIdentity(unittest.TestCase):
    def test_path_identity_and_duplicate_controls_reach_packaged_verifier(self):
        _, config = inputs()
        for kind in ('matching', 'wrong-name', 'duplicate'):
            data = candidate(kind, config)
            with self.subTest(kind=kind, path='class-reader'), ZipFile(io.BytesIO(data)) as jar:
                if kind == 'matching':
                    raw, nodes = game_linkage.read_candidate_classes(jar)
                    self.assertEqual((len(raw), set(nodes)), (1, {'fixture/Caller'}))
                else:
                    with self.assertRaisesRegex(ValueError, 'candidate class path mismatch|duplicate candidate class path'):
                        game_linkage.read_candidate_classes(jar)
            with self.subTest(kind=kind, path='packaged-verifier'), tempfile.TemporaryDirectory() as temp:
                jar = Path(temp) / 'candidate.jar'
                jar.write_bytes(data)
                if kind == 'matching':
                    # The identity gate passed; this intentionally incomplete
                    # fixture has no registered Mixin class.
                    with self.assertRaises(KeyError):
                        verifier.verify(jar, ['fixture'], None)
                else:
                    with self.assertRaisesRegex(ValueError, 'candidate class path mismatch|duplicate candidate class path'):
                        verifier.verify(jar, ['fixture'], None)

    def test_only_absent_or_empty_common_mixin_list_is_supported(self):
        _, config = inputs()
        for common in ('absent', [], ['MissingMixin'], None, {}):
            current = dict(config)
            if common != 'absent':
                current['mixins'] = common
            with self.subTest(common=common), tempfile.TemporaryDirectory() as temp:
                jar = Path(temp) / 'candidate.jar'
                jar.write_bytes(candidate('matching', current))
                if common == 'absent' or common == []:
                    with self.assertRaises(KeyError):
                        verifier.verify(jar, ['fixture'], None)
                else:
                    with self.assertRaisesRegex(ValueError, 'unsupported common Mixin registration'):
                        verifier.verify(jar, ['fixture'], None)


if __name__ == '__main__':
    unittest.main()
