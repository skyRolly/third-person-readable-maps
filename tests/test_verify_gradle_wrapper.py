import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import verify_gradle_wrapper as wrapper


def canonical(version='9.8.2', digest='a'*64):
    return ('distributionBase=GRADLE_USER_HOME\n'
            'distributionPath=wrapper/dists\n'
            f'distributionSha256Sum={digest}\n'
            f'distributionUrl=https\\://services.gradle.org/distributions/gradle-{version}-bin.zip\n'
            'networkTimeout=60000\nretries=3\nretryBackOffMs=500\n'
            'validateDistributionUrl=true\nzipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n')


class WrapperChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root/'gradle/wrapper'; self.path.mkdir(parents=True)
        self.jar = self.path/'gradle-wrapper.jar'; self.jar.write_bytes(b'wrapper fixture')
        self.props = self.path/'gradle-wrapper.properties'; self.props.write_text(canonical())
        self.jar_hash = hashlib.sha256(self.jar.read_bytes()).hexdigest()
        self.fetch = lambda url: self.jar_hash if url.endswith('-wrapper.jar.sha256') else 'a'*64

    def test_current_and_dependabot_canonical_versions(self):
        for version in ('9.8.2', '9.9.0'):
            with self.subTest(version=version):
                self.props.write_text(canonical(version))
                self.assertEqual(wrapper.verify(self.root, self.fetch), version)
                self.props.write_bytes(canonical(version).replace('\n', '\r\n').encode('ascii'))
                self.assertEqual(wrapper.verify(self.root, self.fetch), version)

    def test_integrity_and_failure_paths(self):
        self.jar.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'JAR checksum mismatch'): wrapper.verify(self.root, self.fetch)
        self.jar.write_bytes(b'wrapper fixture')
        self.props.write_text(canonical(digest='b'*64))
        with self.assertRaisesRegex(ValueError, 'distribution checksum'): wrapper.verify(self.root, self.fetch)
        self.props.write_text(canonical())
        with self.assertRaises(OSError): wrapper.verify(self.root, lambda url: (_ for _ in ()).throw(OSError('offline')))
        with self.assertRaisesRegex(ValueError, 'published SHA-256'): wrapper.verify(self.root, lambda url: 'invalid')

    def test_ambiguous_or_unsupported_properties_fail_before_fetch(self):
        good = canonical()
        invalid = [
            good + 'distributionUrl=https\\://services.gradle.org/distributions/gradle-9.9.0-bin.zip\n',
            good + r'distribution\u0055rl=https\://example.invalid/gradle.zip' + '\n',
            good + r'distributionSha256\u0053um=' + 'b'*64 + '\n',
            good + ' distributionUrl=https\\://example.invalid/gradle.zip\n',
            good + 'distributionUrl:https\\://example.invalid/gradle.zip\n',
            good.replace('distributionUrl=https\\://', 'distributionUrl=https\\:\\\n//'),
            good + 'distribution\\=Url=invalid\n',
            good + r'distribution\u00ZZrl=invalid' + '\n',
            good.replace('services.gradle.org', 'example.invalid'),
            good.replace('-bin.zip', '-all.zip'),
            good.replace('validateDistributionUrl=true', 'validateDistributionUrl=false'),
            good.replace('zipStorePath=wrapper/dists', 'zipStorePath=../../other'),
            good.replace('distributionBase=GRADLE_USER_HOME', 'distributionBase=PROJECT'),
            good.replace('distributionSha256Sum='+'a'*64+'\n', ''),
            good + 'unknownProperty=value\n', good + 'networkTimeout 123\n',
        ]
        for data in invalid:
            with self.subTest(data=data[-90:]):
                self.props.write_text(data)
                def forbidden(url): raise AssertionError('invalid properties must not trigger checksum fetch')
                with self.assertRaises((ValueError, UnicodeError)): wrapper.verify(self.root, forbidden)

    def test_previous_parser_accepts_java_unicode_override(self):
        if not shutil.which('javac') or not shutil.which('java'): self.skipTest('JDK required')
        self.props.write_text(canonical() + r'distribution\u0055rl=https\://example.invalid/gradle.zip' + '\n')
        # Reproduce the old line split without contacting either URL.
        old = {}
        for line in self.props.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                if key in old: raise ValueError('duplicate')
                old[key] = value
        self.assertIn('services.gradle.org', old['distributionUrl'])
        java = self.root/'ReadProperties.java'
        java.write_text('import java.io.*; import java.util.*; public class ReadProperties { '
                        'public static void main(String[] a) throws Exception { Properties p=new Properties(); '
                        'try(InputStream i=new FileInputStream(a[0])) { p.load(i); } '
                        'System.out.print(p.getProperty("distributionUrl")); }}')
        subprocess.run(['javac','--release','8',str(java)],check=True,capture_output=True)
        effective = subprocess.check_output(['java','-cp',str(self.root),'ReadProperties',str(self.props)],text=True)
        self.assertEqual(effective, 'https://example.invalid/gradle.zip')
        with self.assertRaises(ValueError): wrapper.verify(self.root, self.fetch)

    def test_canonical_effective_values_match_java_properties(self):
        if not shutil.which('javac') or not shutil.which('java'): self.skipTest('JDK required')
        java = self.root/'PropertiesOracle.java'
        java.write_text('import java.io.*; import java.util.*; public class PropertiesOracle { '
                        'public static void main(String[] a) throws Exception { Properties p=new Properties(); '
                        'try(InputStream i=new FileInputStream(a[0])) { p.load(i); } '
                        'System.out.println(p.getProperty("distributionUrl")); '
                        'System.out.println(p.getProperty("distributionSha256Sum")); }}')
        subprocess.run(['javac','--release','8',str(java)],check=True,capture_output=True)
        for version in ('9.8.2','9.9.0'):
            self.props.write_text(canonical(version))
            checked = wrapper.canonical_properties(self.props.read_bytes())
            actual = subprocess.check_output(['java','-cp',str(self.root),'PropertiesOracle',str(self.props)],text=True).splitlines()
            self.assertEqual(actual, [checked['distributionUrl'].replace('\\:', ':'), checked['distributionSha256Sum']])

    def test_redirects_remain_on_gradle_checksum_hosts_and_same_path(self):
        handler = wrapper.GradleChecksumRedirect(); req = Request(wrapper.BASE+'gradle-9.8.2-bin.zip.sha256')
        redirect = handler.redirect_request(req,None,301,'moved',{},'https://downloads.gradle.org/distributions/gradle-9.8.2-bin.zip.sha256')
        self.assertEqual(redirect.full_url, 'https://downloads.gradle.org/distributions/gradle-9.8.2-bin.zip.sha256')
        for url in ('https://example.invalid/distributions/gradle-9.8.2-bin.zip.sha256',
                    'http://downloads.gradle.org/distributions/gradle-9.8.2-bin.zip.sha256',
                    'https://downloads.gradle.org/distributions/other.sha256'):
            with self.subTest(url=url), self.assertRaises(ValueError): handler.redirect_request(req,None,301,'moved',{},url)

    def test_preflight_failure_prevents_following_build_action(self):
        self.props.write_text(canonical() + r'distribution\u0055rl=https\://example.invalid/gradle.zip' + '\n')
        sentinel = self.root/'gradle-would-have-run'
        command = [sys.executable, str(ROOT/'scripts/verify_gradle_wrapper.py'), '--root', str(self.root)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0: sentinel.write_text('would execute Gradle')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(sentinel.exists())

    def test_workflow_and_windows_entrypoint_preflight_before_gradle(self):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        build, dependency = workflow.split('\n  dependency-graph:', 1)
        command = 'run: python scripts/verify_gradle_wrapper.py'
        self.assertEqual(build.count(command), 1)
        self.assertLess(build.index(command), build.index('gradle/actions/setup-gradle@'))
        self.assertLess(build.index(command), build.index('./gradlew '))
        self.assertLess(build.index(command), build.index('Build-Windows.bat'))
        self.assertEqual(dependency.count(command), 1)
        self.assertLess(dependency.index(command), dependency.index('gradle/actions/dependency-submission@'))
        self.assertNotIn('continue-on-error', build)
        self.assertNotIn('continue-on-error', dependency)
        bat = (ROOT/'Build-Windows.bat').read_text()
        self.assertLess(bat.index('python scripts\\verify_gradle_wrapper.py'), bat.index('call gradlew.bat'))
        self.assertIn('if errorlevel 1', bat)


if __name__ == '__main__':
    unittest.main()
