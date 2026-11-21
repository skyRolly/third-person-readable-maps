import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_supported_apis import verify_lwjgl_member

REF = ('method', 'org/lwjgl/opengl/GL11', 'glIsEnabled', '(I)Z')


class LwjglReferenceTests(unittest.TestCase):
    def node(self, descriptor='(I)Z', access=9):
        return {'name': REF[1], 'members': [{'kind': 'method', 'name': 'glIsEnabled',
                                            'descriptor': descriptor, 'access': access}]}

    def test_accepts_public_static_exact_descriptor(self):
        verify_lwjgl_member(self.node(), REF, '1.14')

    def test_rejects_missing_or_wrong_descriptor(self):
        for node in (None, self.node('(I)V')):
            with self.subTest(node=node), self.assertRaises(ValueError):
                verify_lwjgl_member(node, REF, '1.14')

    def test_rejects_non_public_or_instance_method(self):
        for access in (8, 1):
            with self.subTest(access=access), self.assertRaises(ValueError):
                verify_lwjgl_member(self.node(access=access), REF, '1.14')


if __name__ == '__main__':
    unittest.main()
