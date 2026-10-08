import unittest,json,tempfile
from copy import deepcopy
from pathlib import Path
from cloud_rules_contract import *
from cloud_rules_publisher import notice_observations,monitor,NEWS
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'registry.json').read_text('utf8'))
        manifest=json.loads((ROOT/'public/manifest.json').read_text('utf8'))
        self.pack=json.loads((ROOT/'public'/manifest['rules']).read_text('utf8'))
    def test_baseline_complete(self):self.assertEqual(validate_pack(self.pack,self.registry),self.pack)
    def test_existing_numeric_slot_can_change(self):
        row=deepcopy(self.pack['cards']['1000103']);row['description']=row['description'].replace('3攻','5攻',1)
        after,pending,changed=apply_observations(self.pack,self.registry,[row])
        self.assertFalse(pending);self.assertEqual(changed,[1000103]);self.assertEqual(after['cards']['1000103']['parameters'][0],5)
    def test_mechanism_cannot_be_guessed(self):
        row=deepcopy(self.pack['cards']['1000103']);row['description']+='\n再次行动'
        after,pending,changed=apply_observations(self.pack,self.registry,[row])
        self.assertTrue(pending);self.assertFalse(changed);self.assertEqual(after,self.pack)
    def test_official_known_attack_change_binds_exact_native_family(self):
        notice=dict(url='https://store.steampowered.com/news/app/1948800',contents='Giant Elephant Spirit Sword: 3 ATK ×3 → 5 ATK ×3')
        observations,pending=notice_observations(notice,self.pack,self.registry)
        self.assertFalse(pending);after,failed,changed=apply_observations(self.pack,self.registry,observations,official=True)
        self.assertFalse(failed);self.assertEqual(changed,[1000103,1010103,1020103])
        self.assertEqual(after['cards']['1020103']['parameters'][0],5)
    def test_ambiguous_official_update_does_not_publish(self):
        notice=dict(url='https://store.steampowered.com/news/app/1948800',contents='Giant Elephant Spirit Sword: ATK and Qi changed, gain another action')
        observed,pending=notice_observations(notice,self.pack,self.registry)
        self.assertFalse(observed);self.assertTrue(pending)

    def prepared(self,folder):
        public=folder/'public'
        (public/'rules').mkdir(parents=True)
        (folder/'registry.json').write_text(json.dumps(self.registry),'utf8')
        (public/'rules/baseline.json').write_text(json.dumps(self.pack),'utf8')
        (public/'manifest.json').write_text(json.dumps(dict(schema=1,serial=self.pack['serial'],
            rules='rules/baseline.json',sha256=checksum(self.pack),accepted_notices={})), 'utf8')
        return public

    def test_upstream_health_is_published_without_changing_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);public=self.prepared(folder)
            with patch('cloud_rules_publisher.observations_for_page',return_value=[]):
                result=monitor(folder,reader=lambda url:b'{"appnews":{"newsitems":[]}}',
                    now=datetime(2026,10,8,18,0,tzinfo=timezone.utc))
            manifest=json.loads((public/'manifest.json').read_text('utf8'))
            self.assertEqual(result['state'],'verified')
            self.assertEqual(manifest['monitor_state'],'verified')
            self.assertEqual(manifest['supported_faces'],54)
            self.assertEqual(manifest['sha256'],checksum(self.pack))
            self.assertEqual(manifest['serial'],self.pack['serial'])

    def test_official_source_failure_is_visible_in_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);public=self.prepared(folder)
            def fail(url):raise OSError('official source timeout')
            with patch('cloud_rules_publisher.observations_for_page',return_value=[]):
                result=monitor(folder,reader=fail,now=datetime(2026,10,8,18,0,tzinfo=timezone.utc))
            manifest=json.loads((public/'manifest.json').read_text('utf8'))
            self.assertEqual(result['state'],'partial_source_failure')
            self.assertEqual(manifest['monitor_state'],'partial_source_failure')
            self.assertTrue(manifest['source_errors'])
            self.assertEqual(manifest['sha256'],checksum(self.pack))

if __name__=='__main__':unittest.main()
