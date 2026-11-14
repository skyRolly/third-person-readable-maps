import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import verify_gradle_wrapper as wrapper


class WrapperChecks(unittest.TestCase):
    def test_published_checksums_and_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'gradle/wrapper'; path.mkdir(parents=True)
            jar = path/'gradle-wrapper.jar'; jar.write_bytes(b'wrapper fixture')
            props = path/'gradle-wrapper.properties'
            good = ('distributionUrl=https\\://services.gradle.org/distributions/gradle-9.8.2-bin.zip\n'
                    'distributionSha256Sum='+'a'*64+'\n')
            props.write_text(good)
            jar_hash = hashlib.sha256(jar.read_bytes()).hexdigest()
            def fetch(url): return jar_hash if url.endswith('-wrapper.jar.sha256') else 'a'*64
            self.assertEqual(wrapper.verify(root, fetch), '9.8.2')
            jar.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'JAR checksum mismatch'):
                wrapper.verify(root, fetch)
            jar.write_bytes(b'wrapper fixture')
            props.write_text(good.replace('a'*64, 'b'*64))
            with self.assertRaisesRegex(ValueError, 'distribution checksum'):
                wrapper.verify(root, fetch)
            props.write_text(good.replace('services.gradle.org', 'example.invalid'))
            with self.assertRaisesRegex(ValueError, 'untrusted'):
                wrapper.verify(root, fetch)
            props.write_text(good+good)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                wrapper.verify(root, fetch)


if __name__ == '__main__':
    unittest.main()
