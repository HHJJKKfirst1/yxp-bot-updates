"""Current mechanism pack and complete notice coverage, separate from v3 pins."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cloud_rules_contract import validate_pack,RuleRejected,checksum,apply_observations
from cloud_rules_notice_coverage import balance_inventory
from cloud_rules_publisher import monitor
ROOT=Path(__file__).resolve().parents[1]


class Oct29Tests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'registry.json').read_text('utf8'))
        self.manifest=json.loads((ROOT/'public/manifest.json').read_text('utf8'))
        self.pack=json.loads((ROOT/'public'/self.manifest['rules']).read_text('utf8'))

    def test_complete_data_only_current_native_mechanisms_and_minimum(self):
        self.assertEqual(self.pack['engine_contract'],'numeric-templates-4')
        self.assertEqual(self.manifest['minimum_assistant_version'],'1.1.356')
        self.assertEqual([len(self.pack[k])for k in ('cards','fates','mechanism_cards')],[78,216,29])
        self.assertEqual(validate_pack(self.pack,self.registry),self.pack)
        old=json.loads((ROOT/'public/rules/2026.10.22.6.json').read_text('utf8'))
        self.assertEqual(checksum(old),'77decea0692c8b174a4531681b63cb252605998c86e598fbb6ffa67ea61c2a78')
        self.assertEqual(old['cards'],self.pack['cards'])

    def test_published_item_receipts_match_all_84_native_reviewed_identities(self):
        inventory=json.loads((ROOT/'audits/2026-10-29-notice-inventory.json').read_text('utf8'))
        ledger=json.loads((ROOT/'notice_coverage_reviews.json').read_text('utf8'))
        receipt=ledger['notices'][inventory['gid']]
        self.assertEqual(receipt['source'],inventory['source'])
        self.assertEqual(receipt['balance_sha256'],inventory['balance_sha256'])
        expected={row['item_id']:row['item_sha256']for row in inventory['items']}
        self.assertEqual(len(expected),84)
        self.assertEqual({key:row['item_sha256']for key,row in receipt['items'].items()},expected)
        for row in receipt['items'].values():
            self.assertEqual(row['engine_contract'],'numeric-templates-4')
            self.assertEqual(row['minimum_assistant_version'],'1.1.356')
            self.assertEqual(row['kind'],'mechanism')
            self.assertTrue(row['evidence_sha256'])
            for digest in row['evidence_sha256']:self.assertRegex(digest,r'^[a-f0-9]{64}$')
        # A later announcement must not make this fixed Oct29 receipt test
        # fail and stop the monitor before it can publish the new pending items.
        coverage=self.manifest['announcement_coverage']['notices'][inventory['gid']]
        self.assertEqual([coverage[key]for key in('item_count','reviewed_count','pending_count')],[84,84,0])

    def test_future_numeric_update_keeps_complete_mechanism_snapshot_and_contract4(self):
        row=dict(self.pack['cards']['3000012'],description='施加6层虚弱\n消耗')
        pack,pending,changed=apply_observations(self.pack,self.registry,[row])
        self.assertFalse(pending);self.assertEqual(changed,[3000012])
        self.assertEqual(pack['engine_contract'],'numeric-templates-4')
        self.assertEqual(pack['fates'],self.pack['fates'])
        self.assertEqual(pack['mechanism_cards'],self.pack['mechanism_cards'])

    def test_missing_unreviewed_and_boolean_mechanism_changes_are_rejected(self):
        for kind in ('fates','mechanism_cards'):
            for change in ('missing','value','code'):
                with self.subTest(kind=kind,change=change):
                    value=deepcopy(self.pack);sid=next(iter(value[kind]))
                    if change=='missing':value[kind].pop(sid)
                    elif change=='code':value[kind][sid]['remote_handler']='unreviewed'
                    elif kind=='fates':value[kind][sid]['native']['is_available']=1
                    else:value[kind][sid]['hp_cost']=False
                    with self.assertRaises(RuleRejected):validate_pack(value,self.registry)

    def test_exact_reviewed_gift_mention_does_not_create_a_false_numeric_card_pending(self):
        notice=dict(gid='1847920302233330',title='Synthetic Oct29 gift',date=1793242934,
            url='https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1847920302233330',
            contents='[p]Update at 14:00 today (UTC+8).[/p][h1]Balance Adjustment[/h1][h2]Immortal Fate Adjustments[/h2]'
            '[list][*][p]Heavenly Derivation - Jade Scroll of Yin Symbol: Cultivation cost1 to2, grant1 to2.[/p][/*][/list]')
        inventory=balance_inventory(notice)
        self.assertEqual(len(inventory['items']),1)
        receipt=dict(schema=1,notices={notice['gid']:dict(source=notice['url'],balance_sha256=inventory['balance_sha256'],
            items={r['item_id']:dict(item_sha256=r['item_sha256'],kind='mechanism',engine_contract='numeric-templates-4',minimum_assistant_version='1.1.356',evidence_sha256=['a'*64])for r in inventory['items']})})
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);public=root/'public';(public/'rules').mkdir(parents=True)
            manifest=dict(self.manifest,rules='rules/base.json',accepted_notices={},pending=[])
            manifest.pop('announcement_coverage',None)
            for path,value in [(root/'registry.json',self.registry),(root/'notice_coverage_reviews.json',receipt),
                (public/'rules/base.json',self.pack),(public/'manifest.json',manifest)]:
                path.write_text(json.dumps(value),'utf8')
            body=json.dumps(dict(appnews=dict(newsitems=[notice]))).encode()
            with patch('cloud_rules_publisher.observations_for_page',return_value=[]):
                result=monitor(root,reader=lambda url:body,now=datetime(2026,10,29,8,tzinfo=timezone.utc))
            self.assertEqual(result['pending'],[])
            self.assertEqual(result['announcement_coverage']['latest_reviewed_count'],1)
            self.assertEqual(result['announcement_coverage']['latest_pending_count'],0)
            self.assertEqual(json.loads((public/'manifest.json').read_text('utf8'))['serial'],self.pack['serial'])


if __name__=='__main__':unittest.main()
