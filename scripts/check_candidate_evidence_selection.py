#!/usr/bin/env python3
"""Check retained evidence and flag selections older than monitored candidates."""
import sys

import validate_current_evidence as evidence


def candidate_source_drift(heads, candidates):
    evidence.require(isinstance(heads, dict) and isinstance(candidates, dict) and candidates,
                     'invalid candidate sources')
    pending = []
    for group, candidate in candidates.items():
        evidence.require(group in heads and isinstance(heads[group], dict) and isinstance(candidate, dict),
                         group + ': missing selected or monitored candidate source')
        selected, monitored = heads[group].get('new_head'), candidate.get('candidate_head')
        evidence.checked_id(selected, evidence.COMMIT, group + ': invalid selected source')
        evidence.checked_id(monitored, evidence.COMMIT, group + ': invalid monitored candidate source')
        monitoring = candidate.get('monitoring', {'state': 'candidate'})
        evidence.require(isinstance(monitoring, dict), group + ': invalid monitoring state')
        state = monitoring.get('state')
        evidence.require(state in ('candidate', 'integrated-transition', 'retired-authoritative'),
                         group + ': invalid monitoring state')
        if state != 'candidate':
            pending.append(group + ': verify selected evidence against transitioned source')
        elif selected != monitored:
            pending.append(group + ': selected evidence predates monitored candidate head')
    return pending


def main():
    # Preserve all existing evidence validation, including strict mode, before
    # checking the additional live-monitoring source relationship.
    result = evidence.main()
    if result:
        return result
    try:
        heads = evidence.read('docs/version-consistency-1.0.0/current-heads.json')['groups']
        candidates = evidence.read('docs/legacy-candidate-evidence.json')['groups']
        pending = candidate_source_drift(heads, candidates)
        print('Monitored candidate evidence: ' + ('PENDING: ' + '; '.join(pending) if pending else 'current'))
        return 1 if '--require-complete' in sys.argv[1:] and pending else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Monitored candidate evidence is inconsistent: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
