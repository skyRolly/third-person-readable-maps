"""Keep independently failing Python suites in separate Actions steps."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/credential-guard-tests.yml'


def check_steps(text):
    expected = {
        'Verify live audit evidence': 'python -m unittest discover -s tests -p "test_issue45_live_audits.py" -v',
        'Verify packaged-mod evidence': 'python -m unittest discover -s tests -p "test_issue45_mod_jar_inspection.py" -v',
    }
    for name, command in expected.items():
        match = re.findall(r'(?m)^      - name: ' + re.escape(name) + r'\n        run: ([^\n]+)$', text)
        if match != [command]:
            raise ValueError(name + ' must be an independent step')
    if 'continue-on-error:' in text:
        raise ValueError('test failure suppression is forbidden')


class WorkflowPropagationTests(unittest.TestCase):
    def test_suites_are_independent_steps(self):
        check_steps(WORKFLOW.read_text())

    def test_old_combined_step_is_rejected(self):
        text = WORKFLOW.read_text()
        old = ('      - name: Verify live audit and packaged-mod evidence\n'
               '        run: |\n'
               '          python -m unittest discover -s tests -p "test_issue45_live_audits.py" -v\n'
               '          python -m unittest discover -s tests -p "test_issue45_mod_jar_inspection.py" -v')
        start = text.index('      - name: Verify live audit evidence')
        changed = text[:start] + old + '\n'
        with self.assertRaisesRegex(ValueError, 'independent step'):
            check_steps(changed)


if __name__ == '__main__':
    unittest.main()
