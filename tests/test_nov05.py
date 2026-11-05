"""Nov05 is a new client contract, not a rewrite of the Oct29 pack."""
from copy import deepcopy
import json
from pathlib import Path

import unittest
from cloud_rules_contract import checksum,validate_pack,RuleRejected


ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT/path).read_text('utf8'))


class Nov05Tests(unittest.TestCase):
    def test_current_manifest_and_legacy_pack_are_both_exact(self):
        registry=read('registry.json')
        manifest=read('public/manifest.json')
        current=read('public/rules/2026.11.05.8.json')
        old=read('public/rules/2026.10.29.7.json')
        assert (current['revision'],current['serial'],current['engine_contract'])==(
            '2026.11.05.8',8,'numeric-templates-5')
        assert checksum(current)=='c0d6ff61651209839814ed68ab9bf7f157e63393be3dd7047aeb334c1f4a353d'
        assert len(current['fates'])==218 and len(current['mechanism_cards'])==29
        assert validate_pack(current,registry)==current
        assert checksum(old)=='ff5cce02f020afd29e9c985108415ef3b6b459078cc4145f2b451ebced7a946d'
        assert len(old['fates'])==216 and validate_pack(old,registry)==old
        # Later verified serials and resolved pending notices remain possible.
        assert manifest['serial']>=8
        active=read('public/'+manifest['rules'])
        assert checksum(active)==manifest['sha256'] and validate_pack(active,registry)==active

    def test_unreviewed_mechanism_is_rejected(self):
        registry=read('registry.json')
        for section in ('fates','mechanism_cards'):
            with self.subTest(section=section):
                pack=read('public/rules/2026.11.05.8.json');entry=next(iter(pack[section].values()))
                changed=deepcopy(pack);changed[section]['999999']=deepcopy(entry)
                with self.assertRaises(RuleRejected):validate_pack(changed,registry)
