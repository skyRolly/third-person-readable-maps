"""The coordinator checks source Wrapper configuration before any Gradle action."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WrapperWorkflowTests(unittest.TestCase):
    def test_audit_jobs_use_coordinator_preflight_before_gradle(self):
        for workflow in ('dependency-audit.yml','candidate-dependency-audit.yml'):
            text=(ROOT/'.github/workflows'/workflow).read_text()
            with self.subTest(workflow=workflow):
                before=text.index('run: python3 scripts/verify_gradle_wrapper.py --root source')
                self.assertLess(before,text.index('gradle/actions/dependency-submission@'))
                self.assertNotIn('continue-on-error',text)
                self.assertIn('path: source',text)
                self.assertIn('permissions:\n  contents: read',text)

    def test_release_uses_coordinator_copy_before_gradle_and_no_secrets_in_build(self):
        text=(ROOT/'.github/workflows/release.yml').read_text()
        build=text.split('\n  build:\n',1)[1].split('\n  collect:',1)[0]
        check=build.index('python3 .coordination-tools/scripts/verify_gradle_wrapper.py --root .')
        self.assertLess(build.index('path: .coordination-tools'),check)
        self.assertLess(check,build.index('gradle/actions/setup-gradle@'))
        self.assertLess(check,build.index('./gradlew '))
        self.assertNotIn('continue-on-error',build)
        self.assertNotIn('secrets.',build)

    def test_bad_properties_stop_before_a_build_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'gradle/wrapper';path.mkdir(parents=True)
            (path/'gradle-wrapper.properties').write_text(r'distribution\u0055rl=https\://example.invalid/x.zip'+'\n')
            marker=root/'gradle-executed'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/verify_gradle_wrapper.py'),'--root',str(root)],
                                  capture_output=True,text=True)
            if result.returncode==0: marker.write_text('Gradle would run here')
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
