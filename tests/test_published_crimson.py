"""The published data must agree with independently extracted native values."""
import json,unittest
from pathlib import Path
from cloud_rules_contract import validate_pack,checksum,plain
ROOT=Path(__file__).resolve().parents[1]

class PublishedCrimsonTests(unittest.TestCase):
    def test_exact_three_native_faces_and_other_seventy_five_unchanged(self):
        registry=json.loads((ROOT/'registry.json').read_text('utf8'))
        manifest=json.loads((ROOT/'public/manifest.json').read_text('utf8'))
        pack=validate_pack(json.loads((ROOT/'public'/manifest['rules']).read_text('utf8')),registry)
        before=json.loads((ROOT/'public/rules/2026.10.15.4.json').read_text('utf8'))
        proof=json.loads((ROOT/'audits/2026-10-22-crimson-native.json').read_text('utf8'))
        self.assertEqual(proof['game_build_id'],26125017)
        self.assertEqual(checksum(pack),manifest['sha256'])
        self.assertEqual(len(pack['cards']),78)
        self.assertEqual([row['native_id'] for row in proof['faces']],[1000102,1010102,1020102])
        for rank,native in enumerate(proof['faces'],1):
            row=pack['cards'][str(native['native_id'])]
            self.assertEqual(plain(row['description']),plain(native['description']))
            self.assertEqual(row['parameters'],[1,1,rank,6])
            self.assertEqual([row['name'],row['level'],row['qi_cost'],row['hp_cost']],
                [native['name'],rank,0,0])
        changed=[int(cid) for cid,row in pack['cards'].items() if row!=before['cards'][cid]]
        self.assertEqual(sorted(changed),[1000102,1010102,1020102])

if __name__=='__main__':unittest.main()
