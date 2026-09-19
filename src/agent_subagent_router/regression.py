"""Legacy imports keep their protocol semantics and provenance; never live PASS."""
from .contracts import RouterError, canonical_bytes, hash_bytes


def replay_case(case: dict) -> dict:
    if case.get('provenance') not in ('synthetic', 'historical'):
        raise RouterError('UNRESOLVED_PROVENANCE')
    if case['provenance'] == 'historical' and not case.get('original_invocation_id'):
        raise RouterError('UNRESOLVED_PROVENANCE')
    value = case['input']
    classification = 'HISTORICAL_UNQUALIFIED'
    if value.get('status') == 'DONE_WITH_CONCERNS' and value.get('questions'):
        classification = 'PROTOCOL_CONTRADICTION'
    elif value.get('error') == 'error_max_structured_output_retries':
        classification = 'STRUCTURED_OUTPUT_EXHAUSTED'
    elif value.get('termination_reason') == 'dialogue_protocol_error':
        classification = 'PROTOCOL_ERROR'
    elif value.get('denied_tools') or set(value.get('attempted_tools', [])) - {'Read', 'Glob', 'Grep'}:
        classification = 'TOOL_POLICY_VIOLATION'
    elif value.get('state_file') == 'null':
        classification = 'LEGACY_REPRESENTATION_AMBIGUOUS'
    elif value.get('retry_requested'):
        classification = 'FOLLOWUP_REQUIRES_PARENT'
    elif value.get('terminal') is False:
        classification = 'TERMINAL_MISSING'
    elif set(value.get('required_evidence', [])) - set(value.get('observed_evidence', [])):
        classification = 'EVIDENCE_INCOMPLETE'
    return {'classification': classification, 'original_sha256': hash_bytes(canonical_bytes(value)),
            'normalization': 'none', 'normalizer_version': 1, 'automatic_retry': False,
            'provider_identity': 'NOT_EVALUATED', 'parent_acceptance': 'NOT_EVALUATED',
            'cli_exit_code': value.get('cli_exit'), 'legacy_transport_exit': value.get('transport_exit'),
            'quarantined': classification != 'HISTORICAL_UNQUALIFIED',
            'provenance': case['provenance']}
