"""Small stdlib-only parent gate for the real M8 protocol patch."""
import json
from agent_subagent_router.gemini_protocol import decode_gemini


def stream(ids):
    events = [{'type':'init','model':'gemini-2.5-flash'}]
    events += [{'type':'tool_use','tool_name':'read_file','tool_id':identifier,'parameters':{}} for identifier in ids]
    report = {'findings':[],'proposed_changes':[],'evidence_refs':[],'uncertainties':[],'questions':[]}
    events += [{'type':'message','role':'assistant','content':json.dumps(report)},
               {'type':'result','status':'success'}]
    return b''.join(json.dumps(event).encode()+b'\n' for event in events)


assert decode_gemini(stream(['one','two'])).classification == 'PARSED'
assert decode_gemini(stream(['replayed','replayed'])).classification == 'PROTOCOL_ERROR'
print('Duplicate native tool IDs rejected; distinct IDs accepted.')
