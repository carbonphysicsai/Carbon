"""Reconcile delivery orientation after the substantive owner-policy commit."""
from pathlib import Path
import datetime, json, re, subprocess

root = Path.cwd()
hub = root / 'docs/development/carbon_hub'
p = hub / 'data/hub_data_v2.json'
d = json.loads(p.read_text())
old = d['meta']['authority_snapshot_commit']
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
def repin(value):
    if isinstance(value, str): return value.replace('/blob/' + old + '/', '/blob/' + sha + '/')
    if isinstance(value, list): return [repin(x) for x in value]
    if isinstance(value, dict): return {k: repin(v) for k, v in value.items()}
    return value
d = repin(d)
d['meta']['authority_snapshot_commit'] = sha
d['meta']['captured_at_utc'] = now
d['meta']['authority_notice'] = 'Repository authority controls implementation. OWNER-DX-03 governs delivery: implement the ticket, pass automated checks, and ship without a mandatory human reviewer or GPT receipt. Scientific and security qualification remain separate.'
d['sources']['gpt_review_workflow'] = {'label': 'Owner-directed delivery, superseding the GPT receipt gate', 'url': f'https://github.com/carbonphysicsai/Carbon/blob/{sha}/.agent/DELIVERY_PROTOCOL.md'}
for c in d['authority_source_checks']:
    if c['id'] == 'hub-diff-base-workflow':
        c['required_markers'] = [m.replace('types: [opened, synchronize, reopened, edited, ready_for_review]', 'workflow_dispatch:') for m in c['required_markers']]
    if c['id'] == 'main-ruleset-artifact':
        c['required_markers'] = ['"name": "Carbon main merge gate"', '"context": "Merge gate"', '"required_approving_review_count": 0', '"require_last_push_approval": false']
    if c['id'] == 'gpt-review-gate-workflow':
        c.update(id='owner-dx-03-delivery-policy', path='.agent/DELIVERY_PROTOCOL.md', required_markers=['**Decision:** OWNER-DX-03', 'There is no mandatory human', 'zero required approvals', 'scientific, security, production, LIVE'])
d['current']['parallel_context'].append('OWNER-DX-03 replaces mandatory human/GPT review receipts and repeated CI with tested ticket delivery; scientific-ticket selection is unchanged.')
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n')
p = hub / 'data/change_events.json'; events = json.loads(p.read_text())
events['events'].append({'map_ref': 'SYSTEM/DEVELOPMENT-SEQUENCING', 'event_type': 'decision', 'event_id': 'OWNER-DX-03', 'owner_lane': 'owner', 'status': 'implemented', 'summary': 'The owner removes mandatory human approval and GPT receipts, metadata-triggered full CI, unconditional clean-image builds, duplicate automatic Hub runs, and post-merge full-CI closeout gates while preserving required tests.', 'primary_detail': f'https://github.com/carbonphysicsai/Carbon/blob/{sha}/.agent/DELIVERY_PROTOCOL.md', 'affects': ['WAVE-B/B-05', 'WAVE-B/B-06', 'SYSTEM/AGENT-EXECUTION', 'SYSTEM/CI', 'SYSTEM/PR-MAINTENANCE', 'SYSTEM/DEVELOPMENT-HUB', 'SYSTEM/MATURITY'], 'supersedes': None})
p.write_text(json.dumps(events, indent=2, ensure_ascii=False) + '\n')
p = hub / 'orientation/HUB_UPDATE_PLAYBOOK.md'; s = p.read_text()
s = re.sub(r'Current authority snapshot: `[^`]+`, reconciled [^\n]+\.', f'Current authority snapshot: `{sha}`, reconciled {now}.', s)
s += '\nOWNER-DX-03: batch Hub maintenance before acceptance. Routine code review repairs and external CI results do not require another map event or review-receipt commit.\n'
p.write_text(s)
subprocess.run(['python3', str(hub / 'tools/render_hub.py')], check=True)
