"""Current candidate evidence can advance without rewriting old observations."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import validate_current_evidence as evidence


class EvidenceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.current, self.old, self.scan = 'a'*40, 'b'*40, 'c'*40
        self.digest, self.changed = 'd'*64, 'e'*64
        self.heads = {'g': {'new_head': self.current, 'namespace':'intermediary'}}
        self.versions = {'g': ['v1', 'v2']}
        self.files = {
            'build': {'g': {'source_commit': self.current, 'sha256': self.digest, 'artifact':'fixture.jar',
                            'log_sha256': hashlib.sha256(b'build').hexdigest()}},
            'metadata': {'g': {'source_commit':self.current, 'artifact_sha256':self.digest,
                               'mod_id':'thirdpersonreadablemaps', 'mod_version':'1.0.0',
                               'minecraft':['v1', 'v2'], 'namespace':'intermediary',
                               'artifact':'fixture.jar', 'bytecode_majors':[52], 'java':8}},
            'previous': {'g': {'source_commit': self.old, 'sha256': self.digest}},
            'static': {'results': [{'group':'g', 'version':v, 'source_commit':self.current,
                                    'artifact_sha256':self.digest, 'exit_code':0,
                                    'log_sha256':hashlib.sha256(v.encode()).hexdigest()} for v in self.versions['g']]},
            'logs': {'builds': {'g':'build'}, 'static': {v:v for v in self.versions['g']},
                     'negative': {'unsupported':'rejected'}},
            'negative': {'unsupported': {'group':'g', 'source_commit':self.current,
                         'artifact_sha256':self.digest, 'exit_code':1, 'discriminating_rejection':True,
                         'log_sha256':hashlib.sha256(b'rejected').hexdigest()}},
            'runtime': {'versions': {v:{'group':'g', 'source_commit':self.old, 'artifact_sha256':self.digest}
                                     for v in self.versions['g']}},
            'report': {'source_sha': self.scan}, 'snapshot': {'sha':self.current},
        }
        self.blobs = {'snapshot': json.dumps(self.files['snapshot']).encode(), 'resolution.log': b'BUILD SUCCESSFUL'}
        self.selection = {'schema':1, 'scope':'candidate', 'mod_version':'1.0.0', 'authorizes_release':False, 'validation_logs':'logs',
                          'negative_controls':{'state':'observed', 'record':'negative'}, 'groups':{'g':{
            'source_commit':self.current,
            'build':{'state':'observed', 'record':'build', 'metadata_record':'metadata', 'artifact_sha256':self.digest,
                     'continuity':'same', 'previous_sha256':self.digest,
                     'previous_record':'previous', 'previous_source':self.old},
            'static':{'state':'observed', 'record':'static'},
            'runtime':{'state':'historical-same-artifact', 'record':'runtime'},
            'security':{'state':'retained', 'source_commit':self.scan, 'report':'report',
                        'resolution_kind':'retained-snapshot', 'risk_accepted':False},
        }}}

    def validate(self):
        return evidence.validate(self.heads, self.versions, self.selection, self.files.__getitem__, self.blobs.__getitem__)

    def test_historical_integrity_does_not_read_mutable_current_heads(self):
        import test_hierarchy_historical_evidence as historical
        original = Path.read_text
        def changed_head(path, *args, **kwargs):
            if path.name == 'current-heads.json':
                data = json.loads(original(path, *args, **kwargs))
                for row in data['groups'].values(): row['new_head'] = 'f'*40
                return json.dumps(data)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', changed_head):
            historical.HierarchyHistoricalEvidenceTests('test_builds_and_static_checks_bind_historical_sources').debug()

    def test_same_artifact_continuity_is_recognized_without_approving_release(self):
        self.assertEqual(self.validate(), ['g: current-source security resolution', 'packaged verifier entrypoint fixtures',
                                           'hosted proposal CI', 'candidate rehearsal'])
        self.selection['authorizes_release'] = True
        with self.assertRaisesRegex(ValueError, 'cannot authorize release'): self.validate()

    def test_changed_artifact_marks_old_runtime_missing_without_changing_it(self):
        old = copy.deepcopy(self.files['runtime'])
        row = self.selection['groups']['g']; row['build'].update(artifact_sha256=self.changed, continuity='different')
        self.files['build']['g']['sha256'] = self.changed
        self.files['metadata']['g']['artifact_sha256'] = self.changed
        for result in self.files['static']['results']: result['artifact_sha256'] = self.changed
        self.files['negative']['unsupported']['artifact_sha256'] = self.changed
        row['runtime'] = {'state':'pending'}
        self.assertIn('g: runtime observations', self.validate())
        self.assertEqual(self.files['runtime'], old)

    def test_stale_source_wrong_hash_and_missing_static_are_detected(self):
        row = self.selection['groups']['g']; row['source_commit'] = self.old
        with self.assertRaisesRegex(ValueError, 'obsolete current source'): self.validate()
        row['source_commit'] = self.current; row['build']['artifact_sha256'] = self.changed
        with self.assertRaisesRegex(ValueError, 'build record does not match'): self.validate()
        row['build']['artifact_sha256'] = self.digest; row['static'] = {'state':'pending'}
        self.assertIn('g: static verification', self.validate())

    def test_continuity_can_use_a_grouped_historical_index(self):
        self.files['historical-index'] = {'groups': self.files['previous']}
        build = self.selection['groups']['g']['build']
        build['previous_record'] = 'historical-index'
        build['previous_record_field'] = 'groups'
        self.validate()
        build['previous_record_field'] = 'unexpected'
        with self.assertRaisesRegex(ValueError, 'invalid historical build index'):
            self.validate()

    def test_historical_runtime_cannot_be_relabelled_fresh(self):
        self.selection['groups']['g']['runtime']['state'] = 'fresh'
        with self.assertRaisesRegex(ValueError, 'cannot be relabeled fresh'): self.validate()
        for obs in self.files['runtime']['versions'].values():
            obs.update(source_commit=self.current, execution_kind='fresh')
        self.validate()

    def test_security_report_keeps_scan_source_and_requery_is_not_resolution(self):
        security = self.selection['groups']['g']['security']
        security['source_commit'] = self.current
        with self.assertRaisesRegex(ValueError, 'security report source mismatch'): self.validate()
        security['source_commit'] = self.scan
        security['state'] = 'fresh-resolution'; security['resolution_kind'] = 'osv-requery'
        with self.assertRaisesRegex(ValueError, 'not a fresh dependency resolution'): self.validate()

    def test_fresh_resolution_needs_source_bound_snapshot_and_log(self):
        security = self.selection['groups']['g']['security']
        self.files['report']['source_sha'] = self.current
        security.update(state='fresh-resolution', source_commit=self.current,
                        resolution_kind='fresh-gradle-resolution', snapshot='snapshot', resolution_record='resolution')
        self.files['resolution'] = {'source_commit':self.current, 'kind':'fresh-gradle-resolution',
                                    'log':'resolution.log', 'log_sha256':hashlib.sha256(self.blobs['resolution.log']).hexdigest(),
                                    'snapshot_sha256':hashlib.sha256(self.blobs['snapshot']).hexdigest()}
        self.assertNotIn('g: current-source security resolution', self.validate())
        self.blobs['resolution.log'] = b'not the recorded run'
        with self.assertRaisesRegex(ValueError, 'resolution evidence hash mismatch'): self.validate()

    def test_bundled_fresh_audit_checks_source_scope_and_failing_status(self):
        self.heads['g']['branch'] = 'candidate/mc-g'
        snapshot = json.dumps({'sha':self.current, 'ref':'refs/heads/candidate/mc-g'})
        report = json.dumps({'source_sha':self.current, 'group':'g', 'risk_acceptance':False,
                             'snapshot_ref':'refs/heads/candidate/mc-g',
                             'status':'complete-unreviewed-candidate-scan',
                             'matches':[{'failing':True}], 'resolved_needing_review':[]})
        log, audit_log = 'Verified Gradle wrapper checksums\nBUILD SUCCESSFUL', 'unresolved findings'
        entry = {'snapshot':snapshot, 'report':report, 'resolution_log':log, 'audit_log':audit_log,
                 'resolution':{'source_commit':self.current, 'kind':'fresh-gradle-resolution', 'audit_exit':1,
                               'snapshot_sha256':hashlib.sha256(snapshot.encode()).hexdigest(),
                               'log_sha256':hashlib.sha256(log.encode()).hexdigest(),
                               'report_sha256':hashlib.sha256(report.encode()).hexdigest(),
                               'audit_log_sha256':hashlib.sha256(audit_log.encode()).hexdigest()}}
        security = self.selection['groups']['g']['security']
        security.update(state='fresh-resolution', source_commit=self.current, bundle='bundle',
                        resolution_kind='fresh-gradle-resolution')
        def write_bundle():
            self.blobs['bundle'] = gzip.compress(json.dumps({'schema':1, 'groups':{'g':entry}}).encode(), mtime=0)
            security['bundle_sha256'] = hashlib.sha256(self.blobs['bundle']).hexdigest()
        write_bundle()
        self.assertNotIn('g: current-source security resolution', self.validate())
        entry['resolution']['audit_exit'] = 0; write_bundle()
        with self.assertRaisesRegex(ValueError, 'does not reflect unresolved findings'): self.validate()
        entry['resolution']['audit_exit'] = 1; entry['resolution_log'] = log + ' modified'; write_bundle()
        with self.assertRaisesRegex(ValueError, 'resolution evidence hash mismatch'): self.validate()
        entry['resolution_log'] = log; entry['snapshot'] = snapshot.replace('candidate/mc-g', 'candidate/other'); write_bundle()
        with self.assertRaisesRegex(ValueError, 'snapshot branch mismatch'): self.validate()
        self.blobs['bundle'] += b'corrupt'
        with self.assertRaises((ValueError, OSError)): self.validate()

    def test_logs_and_continuity_references_are_checked(self):
        self.files['logs']['static']['v1'] = 'altered'
        with self.assertRaisesRegex(ValueError, 'static log hash mismatch'): self.validate()
        self.files['logs']['static']['v1'] = 'v1'
        self.files['previous']['g']['sha256'] = self.changed
        with self.assertRaisesRegex(ValueError, 'continuity reference'): self.validate()

    def test_pending_build_is_visible_and_cannot_carry_a_fresh_claim(self):
        row = self.selection['groups']['g']; row['build'] = {'state':'pending'}
        row['static'] = {'state':'pending'}; row['runtime'] = {'state':'pending'}
        self.selection['negative_controls'] = {'state':'pending'}
        self.assertIn('g: build', self.validate())
        row['static'] = {'state':'observed'}
        with self.assertRaisesRegex(ValueError, 'require an observed artifact'): self.validate()

    def test_candidate_rehearsal_checks_manifest_checksums_and_code(self):
        self.heads['g']['branch'] = 'candidate/mc-g'
        self.files['plan'] = {'version':'1.0.0', 'groups':{'g':{'commit':self.current,
                                                               'source_branch':'candidate/mc-g'}}}
        self.files['manifest'] = {'candidate':True, 'version':'1.0.0', 'coordinator_sha':self.old,
                                  'groups':[{'id':'g', 'branch':'candidate/mc-g', 'source_commit':self.current,
                                             'sha256':self.digest, 'artifact':'fixture.jar', 'java':8,
                                             'namespace':'intermediary', 'minecraft':['v1','v2']}]}
        self.files['config'] = {'groups':{'g':{'minecraft':['v1','v2'], 'namespace':'intermediary',
                                                'java':8, 'build_jdk':'fixture'}}}
        self.blobs.update({'manifest':json.dumps(self.files['manifest']).encode(), 'release.py':b'release',
                           'config':json.dumps(self.files['config']).encode(), 'base-runner':b'old-input',
                           'rehearsal/rehearsal.log':b'complete'})
        matrix = (json.dumps(evidence.release.matrix(self.files['config'], self.files['plan']), indent=2)+'\n').encode()
        self.files['rehearsal/index.json'] = {
            'candidate':True, 'authorizes_release':False, 'coordinator_code_commit':self.old,
            'coordinator_code_sha256':{'release.py':hashlib.sha256(b'release').hexdigest()},
            'runner_base':'base-runner', 'runner_base_sha256':hashlib.sha256(b'old-input').hexdigest(),
            'runner_substitutions':{'old':'new'}, 'runner_sha256':hashlib.sha256(b'new-input').hexdigest(),
            'candidate_compatibility_record':'config',
            'candidate_compatibility_sha256':hashlib.sha256(self.blobs['config']).hexdigest(),
            'candidate_matrix_sha256':hashlib.sha256(matrix).hexdigest(),
            'log_sha256':hashlib.sha256(b'complete').hexdigest(),
            'harness_controls':['missing-static-evidence','failed-static-evidence','missing-wrapper-preflight-evidence'],
            'other_controls':1}
        self.files['controls'] = {name:'rejected' for name in
                                  ('missing-static-evidence','failed-static-evidence',
                                   'missing-wrapper-preflight-evidence','production-control')}
        self.blobs['checksums'] = (self.digest+'  fixture.jar\n'+
                                   hashlib.sha256(self.blobs['manifest']).hexdigest()+'  release-manifest.json\n').encode()
        self.selection['candidate_rehearsal'] = {'state':'observed', 'index':'rehearsal/index.json',
                                                  'manifest':'manifest', 'plan':'plan',
                                                  'checksums':'checksums', 'controls':'controls'}
        self.validate()
        index = self.files['rehearsal/index.json']
        index['runner_substitutions'] = {}
        index['runner_sha256'] = index['runner_base_sha256']
        self.validate()
        original = self.blobs['checksums']; self.blobs['checksums'] = original.replace(self.digest.encode(), self.changed.encode())
        with self.assertRaisesRegex(ValueError, 'candidate rehearsal source or artifact mismatch'): self.validate()
        self.blobs['checksums'] = original; self.blobs['release.py'] = b'changed'
        with self.assertRaisesRegex(ValueError, 'coordinator code changed'): self.validate()

    def test_checked_in_current_selection_is_consistent(self):
        heads = evidence.read('docs/version-consistency-1.0.0/current-heads.json')['groups']
        candidates = evidence.read('docs/legacy-candidate-evidence.json')['groups']
        maintenance = evidence.read('release/maintenance-targets.json')['groups']
        versions = {group: row['versions'] for group, row in candidates.items()}
        versions.update({group: row['minecraft'] for group, row in maintenance.items()})
        selection = evidence.read('docs/version-consistency-1.0.0/current-evidence.json')
        evidence.validate(heads, versions, selection, evidence.read, evidence.read_blob)


if __name__ == '__main__':
    unittest.main()
