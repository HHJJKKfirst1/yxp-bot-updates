"""Exercise an unmodified installed engine with old and new immutable pins.

No game attachment, account data or game inputs. Pass --runtime explicitly.
"""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();runtime=Path(args.runtime).resolve();cloud=Path(__file__).resolve().parents[1]
    sys.path.append(str(cloud))
    from cloud_rules_contract import checksum
    manifest=json.loads((cloud/'public/manifest.json').read_text('utf8'))
    new=cloud/'public'/manifest['rules'];old=cloud/'public/rules/2026.10.15.4.json'
    reports=[]
    for target,attack,caps in [(old,5,[2,3,4]),(new,6,[1,2,3])]:
        pack=json.loads(target.read_text('utf8'))
        env=dict(os.environ,YXP_NUMERIC_RULES_PINNED=json.dumps(dict(path=str(target),sha256=checksum(pack))))
        script='''import json,sys
from pathlib import Path
r=Path.cwd();sys.path[:0]=[str(r/'joint_repair_artifacts'),str(r)]
from card_level_catalog import native_card,description_for
from yisim_damage_simulator import simulate_scenarios
from simulation_hand import card_spec
from cloud_rules_runtime import active_pack
pack=active_pack();cases=[];keys=[]
for rank in (1,2,3):
 cid=1000102+(rank-1)*10000;card=native_card(cid)
 assert card['description']==pack['cards'][str(cid)]['description']
 assert description_for(card['name'],rank)['description']==card['description']
 for prior in (0,1,2,3,9):
  cases.append(dict(a_first=True,turns=1,deck_slots=2,a=dict(cards=[card_spec(card)],hp=100,max_hp=100,engine_fields={'unrestrained_sword_count':prior}),b=dict(cards=['普通攻击'],hp=100,max_hp=100)))
  keys.append((rank,prior))
rows=simulate_scenarios(cases,timeout=30)
assert len(rows)==len(keys)
out=[]
for (rank,prior),row in zip(keys,rows):
 assert row['ok'],row
 cap=pack['cards'][str(1000102+(rank-1)*10000)]['parameters'][2]
 bonus=min(prior,cap)
 assert row['final']['a']['increase_atk']==bonus,row
 assert row['damage_to_hp']['b']==ATTACK+bonus,row
 assert row['numeric_rules_revision']==pack['revision']
 out.append(dict(rank=rank,prior=prior,bonus=bonus,damage=row['damage_to_hp']['b']))
print(json.dumps(dict(revision=pack['revision'],cases=out)))
'''.replace('ATTACK',str(attack))
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',script],cwd=runtime,env=env,capture_output=True,text=True,encoding='utf8',timeout=60)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        reports.append(json.loads(result.stdout.strip().splitlines()[-1]))
    # Client transaction and per-match pin isolation use the actual installed code.
    script='''import json,sys,tempfile,shutil
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root/'joint_repair_artifacts'),str(root)]
from cloud_rules_client import refresh,pin_for_match,active
from cloud_rules_contract import checksum
manifest=json.loads(Path(sys.argv[1]).read_text('utf8'));pack=json.loads(Path(sys.argv[2]).read_text('utf8'))
with tempfile.TemporaryDirectory() as temp:
 project=Path(temp)
 for name in ['cloud_rules_registry.json','cloud_rules_baseline.json','release_notes.json']:shutil.copy2(root/name,project/name)
 old=pin_for_match(project);old_bytes=Path(old['path']).read_bytes()
 reader=lambda url:manifest if '/manifest.json' in url else pack
 result=refresh(project,reader=reader,force=True)
 assert result['state']=='verified' and result['pending']==[] and result['updated'],result
 new=pin_for_match(project);assert new['serial']==6 and old['serial']==4
 assert Path(old['path']).read_bytes()==old_bytes
 assert active(project)==pack
 bad=dict(manifest,serial=7,sha256='0'*64)
 failed=refresh(project,reader=lambda url:bad if '/manifest.json' in url else pack,force=True)
 assert failed['state']=='cached' and active(project)==pack
 assert not refresh(project,reader=reader,force=True)['updated']
 print(json.dumps(dict(old_serial=old['serial'],new_serial=new['serial'],old_pin_unchanged=True,corrupt_rejected=True,idempotent=True)))
'''
    result=subprocess.run([sys.executable,'-B','-X','utf8','-c',script,str(cloud/'public/manifest.json'),str(new)],cwd=runtime,capture_output=True,text=True,encoding='utf8',timeout=30)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    report=dict(engine_unchanged=True,game_input_sent=False,combat_cases=sum(len(r['cases']) for r in reports),combat=reports,client=json.loads(result.stdout.strip().splitlines()[-1]))
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(combat_cases=report['combat_cases'],client=report['client'])))

if __name__=='__main__':main()
