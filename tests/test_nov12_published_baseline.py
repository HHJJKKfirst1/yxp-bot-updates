"""Serial 9 is the installed native baseline, with old snapshots still valid.

Serial 8 was left in the public manifest after the assistant adopted serial 9.
The new package is bound to the same local data and keeps strict identity
checks for both old and new protocol versions.
"""
import json
from pathlib import Path
import unittest

from cloud_rules_contract import RuleRejected, checksum, validate_pack

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding='utf8'))


class Nov12PublishedBaseline(unittest.TestCase):
    def test_new_manifest_matches_exact_installed_baseline(self):
        registry = load('registry.json')
        manifest = load('public/manifest.json')
        pack = validate_pack(load('public/rules/2026.11.12.9.json'), registry)
        self.assertEqual((pack['revision'], pack['serial'], pack['engine_contract']),
                         ('2026.11.12.9', 9, 'numeric-templates-6'))
        self.assertEqual(checksum(pack), '8b78ce823933b25c54f8f0e316e08dec934bf0515819cbdbbde2379b2e2cf9b9')
        # Later publisher runs may legitimately advance serial 9 to a newer
        # verified candidate; when 9 is current it must match exactly.
        self.assertGreaterEqual(manifest['serial'], 9)
        if manifest['serial'] == 9:
            self.assertEqual(manifest['sha256'], checksum(pack))
            self.assertEqual(manifest['rules'], 'rules/2026.11.12.9.json')
        self.assertEqual(len(pack['fates']), 763)
        self.assertEqual(len(pack['mechanism_cards']), 29)

    def test_previous_protocol_remains_valid_and_tampering_is_rejected(self):
        registry = load('registry.json')
        previous = validate_pack(load('public/rules/2026.11.05.8.json'), registry)
        self.assertEqual(previous['serial'], 8)
        pack = load('public/rules/2026.11.12.9.json')
        next(iter(pack['fates'].values()))['native']['name'] = 'changed'
        with self.assertRaises(RuleRejected):
            validate_pack(pack, registry)
