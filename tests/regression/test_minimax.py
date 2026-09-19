import json
from pathlib import Path

import pytest

from agent_subagent_router.contracts import canonical_bytes, hash_bytes
from agent_subagent_router.regression import replay_case


CASES = json.loads((Path(__file__).parent/'fixtures/minimax-synthetic.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_legacy_regressions_never_promote_historical_assertions(case):
    assert hash_bytes(canonical_bytes(case['input'])) == case['input_sha256']
    result = replay_case(case)
    assert result['classification'] == case['expected']
    assert result['provider_identity'] == 'NOT_EVALUATED'
    assert result['parent_acceptance'] == 'NOT_EVALUATED'
    assert result['automatic_retry'] is False
    assert result['original_sha256'] == case['input_sha256']
    assert case['provenance'] == 'synthetic'


def test_valid_historical_receipt_still_is_not_new_live_pass():
    case = {'id': 'history', 'provenance': 'historical', 'input': {'cli_exit': 0, 'status': 'DONE'},
            'source_locator': 'sanitized/example', 'original_invocation_id': 'old-invocation'}
    assert replay_case(case)['classification'] == 'HISTORICAL_UNQUALIFIED'
