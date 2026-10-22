"""Oct 22 changed Crimson Sky's cap, not its printed attack slot."""
import json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from cloud_rules_contract import apply_observations,checksum,validate_pack
from cloud_rules_publisher import notice_observations,monitor,notice_hash

ROOT=Path(__file__).resolve().parents[1]
IDS=[1000102,1010102,1020102]

class CrimsonCapTests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'registry.json').read_text('utf8'))
        self.pack=json.loads((ROOT/'public/rules/2026.10.15.4.json').read_text('utf8'))
        self.notice=dict(gid='1847286114031033',date=1792638418,title='Update on Oct. 22',
            url='https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1847286114031033',
            contents='[p]Update at 14:00 today (UTC+8).[/p][p]Unrestrained Sword - Crimson Sky: Max ATK increase 2/3/4 → 1/2/3 stacks[/p]')

    def test_cap_adjustment_preserves_attack_and_every_other_face(self):
        rows,pending=notice_observations(self.notice,self.pack,self.registry)
        self.assertEqual(pending,[])
        self.assertEqual([r['native_id'] for r in rows],IDS)
        after,rejected,changed=apply_observations(self.pack,self.registry,rows,official=True)
        self.assertEqual(rejected,[]);self.assertEqual(changed,IDS)
        for rank,cid in enumerate(IDS,1):
            row=after['cards'][str(cid)]
            self.assertEqual(row['parameters'],[1,1,rank,5])
            self.assertEqual(row['description'],f'每用过1次狂剑获得1层加攻（最多{rank}）\n5攻')
        for cid,row in self.pack['cards'].items():
            if int(cid) not in IDS:self.assertEqual(after['cards'][cid],row)
        validate_pack(after,self.registry)

    def test_attack_change_still_uses_attack_slot(self):
        n={**self.notice,'contents':'Unrestrained Sword - Crimson Sky: 5 ATK → 6 ATK'}
        rows,pending=notice_observations(n,self.pack,self.registry)
        self.assertEqual(pending,[])
        after,rejected,changed=apply_observations(self.pack,self.registry,rows,official=True)
        self.assertEqual(rejected,[]);self.assertEqual(changed,IDS)
        for rank,cid in enumerate(IDS,2):self.assertEqual(after['cards'][str(cid)]['parameters'],[1,1,rank,6])

    def test_unknown_before_value_is_never_silenced(self):
        n={**self.notice,'contents':self.notice['contents'].replace('2/3/4 →','7/8/9 →')}
        rows,pending=notice_observations(n,self.pack,self.registry)
        self.assertEqual(rows,[])
        self.assertEqual([p['native_id'] for p in pending],IDS)
        self.assertEqual({p['reason'] for p in pending},{'official_before_value_mismatch'})

    def test_unknown_red_property_or_new_mechanism_needs_review(self):
        for change in ['Qi 2/3/4 → 1/2/3','Max ATK increase 2/3/4 → 1/2/3 stacks; gain another action']:
            with self.subTest(change=change):
                n={**self.notice,'contents':'Unrestrained Sword - Crimson Sky: '+change}
                rows,pending=notice_observations(n,self.pack,self.registry)
                self.assertEqual(rows,[]);self.assertTrue(pending)

    def test_following_unregistered_bullet_cannot_change_red_binding(self):
        n={**self.notice,'contents':self.notice['contents']+'[p]Mirage: Spiritage Sword: 3/5/7 → 3/6/9 ATK[/p]'}
        rows,pending=notice_observations(n,self.pack,self.registry)
        self.assertEqual(pending,[])
        after,rejected,changed=apply_observations(self.pack,self.registry,rows,official=True)
        self.assertEqual(rejected,[]);self.assertEqual(changed,IDS)
        self.assertEqual([after['cards'][str(cid)]['parameters'][2] for cid in IDS],[1,2,3])

    def test_monitor_repeat_delayed_wiki_and_immutable_old_pack(self):
        original=deepcopy(self.pack)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);public=folder/'public';(public/'rules').mkdir(parents=True)
            (folder/'registry.json').write_text(json.dumps(self.registry),'utf8')
            old_path=public/'rules/old.json';old_path.write_text(json.dumps(self.pack),'utf8')
            old_bytes=old_path.read_bytes()
            manifest=dict(schema=1,serial=4,revision=self.pack['revision'],engine_contract=self.pack['engine_contract'],
                rules='rules/old.json',sha256=checksum(self.pack),accepted_notices={})
            (public/'manifest.json').write_text(json.dumps(manifest),'utf8')
            raw=json.dumps({'appnews':{'newsitems':[self.notice]}}).encode('utf8')
            stale=[dict(self.pack['cards'][str(cid)]) for cid in IDS]
            with patch('cloud_rules_publisher.observations_for_page',return_value=stale):
                first=monitor(folder,reader=lambda u:raw,now=datetime(2026,10,22,6,30,tzinfo=timezone.utc))
                self.assertEqual(first['pending'],[]);self.assertEqual(first['changed_native_ids'],IDS)
                current=json.loads((public/'manifest.json').read_text('utf8'))
                self.assertEqual(current['serial'],5)
                self.assertEqual(current['accepted_notices'][self.notice['gid']],notice_hash(self.notice))
                second=monitor(folder,reader=lambda u:raw,now=datetime(2026,10,22,6,31,tzinfo=timezone.utc))
                self.assertEqual(second['pending'],[]);self.assertEqual(second['changed_native_ids'],[])
                self.assertEqual(json.loads((public/'manifest.json').read_text('utf8'))['serial'],5)
            self.assertEqual(old_path.read_bytes(),old_bytes);self.assertEqual(self.pack,original)

    def test_already_applied_cap_can_be_verified_without_new_serial(self):
        rows,pending=notice_observations(self.notice,self.pack,self.registry);self.assertEqual(pending,[])
        after,failed,_=apply_observations(self.pack,self.registry,rows,official=True);self.assertEqual(failed,[])
        rows,pending=notice_observations(self.notice,after,self.registry)
        self.assertEqual(pending,[]);self.assertEqual([r['native_id'] for r in rows],IDS)
        again,failed,changed=apply_observations(after,self.registry,rows,official=True)
        self.assertEqual(failed,[]);self.assertEqual(changed,[]);self.assertEqual(again,after)

if __name__=='__main__':unittest.main()
