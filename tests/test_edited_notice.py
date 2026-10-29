"""Replay edited announcements against independent native-face receipts."""
import json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from cloud_rules_contract import checksum,apply_observations
from cloud_rules_publisher import notice_hash,notice_observations,monitor,replace_number
ROOT=Path(__file__).resolve().parents[1]
class EditedNoticeTests(unittest.TestCase):
 def setUp(self):
  self.registry=json.loads((ROOT/'registry.json').read_text('utf8'))
  self.manifest=json.loads((ROOT/'public/manifest.json').read_text('utf8'))
  # This isolated Oct15 replay has no later announcement inventory.
  # Preserve the pending==[] assertion for its one explicit source only.
  self.manifest.pop('announcement_coverage',None)
  # This receipt regression replays the exact serial-4 announcement baseline,
  # even after an unrelated current cloud package advances its serial.
  self.pack=json.loads((ROOT/'public/rules/2026.10.15.4.json').read_text('utf8'))
  self.manifest.update(serial=4,revision=self.pack['revision'],sha256=checksum(self.pack))
  self.notice=json.loads((ROOT/'tests/oct15_edited_notice_fixture.json').read_text('utf8'))
  self.ids={f['native_id'] for f in json.loads((ROOT/'tests/oct15_native_fixture.json').read_text('utf8'))['faces']}
 def observe(self,notice=None,pack=None):return notice_observations(notice or self.notice,pack or self.pack,self.registry)
 def prepared(self,folder):
  public=folder/'public';(public/'rules').mkdir(parents=True)
  (folder/'registry.json').write_text(json.dumps(self.registry),'utf8')
  (public/'rules/baseline.json').write_text(json.dumps(self.pack),'utf8')
  (public/'manifest.json').write_text(json.dumps({**self.manifest,'rules':'rules/baseline.json','accepted_notices':{}}),'utf8')
  return public
 def run_monitor(self,folder,notice,now=None):
  raw=json.dumps({'appnews':{'newsitems':[notice]}}).encode('utf8')
  with patch('cloud_rules_publisher.observations_for_page',return_value=[]):
   return monitor(folder,reader=lambda url:raw,now=now or datetime(2026,10,15,9,tzinfo=timezone.utc))
 def test_verifies_all_thirty_faces_and_preserves_rules_and_echo_disclosure(self):
  rows,pending=self.observe();self.assertEqual(pending,[]);self.assertEqual({r['native_id'] for r in rows},self.ids)
  after,rejected,changed=apply_observations(self.pack,self.registry,rows,official=True)
  self.assertEqual(rejected,[]);self.assertEqual(changed,[]);self.assertEqual(after,self.pack)
  self.assertEqual(after['cards']['8000012']['template'],'echo_heal_only');self.assertEqual(after['client_notes'],self.pack['client_notes'])
 def test_repeated_body_edits_are_idempotent_without_a_new_rule_serial(self):
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp);public=self.prepared(folder)
   for index in range(3):
    notice={**self.notice,'contents':'[p]Outfit information revision '+str(index)+'[/p]'+self.notice['contents']}
    result=self.run_monitor(folder,notice);current=json.loads((public/'manifest.json').read_text('utf8'))
    self.assertEqual(result['pending'],[]);self.assertEqual(result['changed_native_ids'],[])
    self.assertEqual(current['accepted_notices'][notice['gid']],notice_hash(notice))
    self.assertEqual(current['serial'],4);self.assertEqual(current['sha256'],checksum(self.pack))
 def test_burn_hp_adjustment_targets_slot_zero_without_changing_scaling(self):
  pack=deepcopy(self.pack)
  for rank in range(3):
   row=pack['cards'][str(7000113+rank*10000)];row['description']=replace_number(row['description'],0,[12,15,18][rank]);row['parameters'][0]=[12,15,18][rank]
  n=dict(url=self.notice['url'],contents='Fire Spirit - Burn to Ashes: Reduce enemy’s HP & Max HP by 12/15/18 → 9/12/15.')
  rows,pending=self.observe(n,pack);self.assertEqual(pending,[])
  after,rejected,changed=apply_observations(pack,self.registry,rows,official=True)
  self.assertEqual(rejected,[]);self.assertEqual(changed,[7000113,7010113,7020113])
  for rank in range(3):self.assertEqual(after['cards'][str(7000113+rank*10000)],self.pack['cards'][str(7000113+rank*10000)])
 def test_earth_is_bounded_before_the_following_water_bullet_and_zero_is_valid(self):
  n=dict(url=self.notice['url'],contents='[list][*][p]Earth Spirit - Chasing Dust Step: Def +2/8/14 → 0/5/10.[/p][/*][*][p]Water Spirit - Falling Rain: HP +8/10/12 → 10/13/16.[/p][/*][/list]')
  rows,pending=self.observe(n);self.assertEqual(pending,[])
  self.assertEqual([r['native_id'] for r in rows],[7000114,7010114,7020114]);self.assertEqual(rows[0]['parameters'][0],0)
 def test_changed_number_new_mechanism_and_extra_balance_bullet_require_review(self):
  for old,new in [('9/12/15.','8/12/15.'),('Def +2/8/14','Again act; Def +2/8/14'),('[h1]Other season information','[*][p]Unknown card: gain another action.[/p][/*][h1]Other season information')]:
   with self.subTest(change=new):
    self.assertIn(old,self.notice['contents']);rows,pending=self.observe({**self.notice,'contents':self.notice['contents'].replace(old,new,1)})
    self.assertEqual(rows,[]);self.assertEqual(pending[0]['reason'],'reviewed_balance_changed')
 def test_every_native_face_cost_is_bound_to_the_receipt(self):
  for cid in sorted(self.ids):
   with self.subTest(native_id=cid):
    pack=deepcopy(self.pack);pack['cards'][str(cid)]['hp_cost']+=1
    rows,pending=self.observe(pack=pack);self.assertEqual(rows,[]);self.assertEqual(pending[0]['reason'],'reviewed_native_faces_changed')
 def test_parameter_template_or_identity_drift_cannot_borrow_receipt(self):
  for key,value in [('parameters',[99]),('template','unknown'),('native_id',384)]:
   with self.subTest(field=key):
    pack=deepcopy(self.pack);pack['cards']['383'][key]=value
    rows,pending=self.observe(pack=pack);self.assertEqual(rows,[]);self.assertEqual(pending[0]['reason'],'reviewed_native_faces_changed')
 def test_known_card_change_outside_balance_is_not_hidden(self):
  rows,pending=self.observe({**self.notice,'contents':self.notice['contents']+'[p]Giant Elephant Spirit Sword: gain another action.[/p]'})
  self.assertEqual(rows,[]);self.assertEqual(pending[0]['reason'],'card_change_outside_reviewed_balance')
 def test_missing_or_duplicate_balance_heading_cannot_use_receipt(self):
  for contents in [self.notice['contents'].replace('Balance Adjustments','Updates'),self.notice['contents']+'[h2]Balance Adjustments[/h2]']:
   with self.subTest(contents=contents[:60]):
    rows,pending=self.observe({**self.notice,'contents':contents});self.assertEqual(rows,[]);self.assertTrue(pending)
 def test_wrong_source_or_legacy_engine_cannot_borrow_receipt(self):
  for n,p in [({**self.notice,'url':'https://example.invalid/notice'},self.pack),(self.notice,{**self.pack,'engine_contract':'numeric-templates-1'})]:
   with self.subTest(source=n['url']):
    rows,pending=self.observe(n,p);self.assertEqual(rows,[]);self.assertTrue(pending)
 def test_future_effective_time_still_prevents_acceptance(self):
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp);public=self.prepared(folder)
   result=self.run_monitor(folder,self.notice,datetime(2026,10,15,2,tzinfo=timezone.utc))
   self.assertEqual(result['pending'][0]['reason'],'announced_rule_not_effective_yet')
   self.assertNotIn(self.notice['gid'],json.loads((public/'manifest.json').read_text('utf8'))['accepted_notices'])
 def test_unrelated_face_updates_do_not_invalidate_thirty_face_receipt(self):
  pack=deepcopy(self.pack);row=pack['cards']['1000103'];row['description']=replace_number(row['description'],0,5);row['parameters'][0]=5
  rows,pending=self.observe(pack=pack);self.assertEqual(pending,[]);self.assertEqual({r['native_id'] for r in rows},self.ids)
