"""Exact Nov 12 announcement deltas checked against the already installed engine.

These cover literal changed values and existing exact contracts, not every
new or unverified mechanism. In particular the native five-element strike
conflict remains unreviewed; actual game input is never sent.
"""
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(os.environ['YXP_AUDIT_ENGINE_ROOT']).resolve()
sys.path.append(str(ROOT / 'joint_repair_artifacts'))
sys.path.append(str(ROOT))

from baijia_catalog import catalog
from baijia_preparation_events import describe, apply
from test_hidden_effects_v339 import card, scene
from yisim_damage_simulator import CardResolver, simulate_scenarios


def test_sword_shadow_all_three_native_grades_and_defense_caps():
    scenarios = []
    for cid in (1000107, 1010107, 1020107):
        state = scene([card(cid)]); state['a']['qi'] = 30
        scenarios.append(state)
    for result, intent, defense in zip(simulate_scenarios(scenarios, timeout=30), (1, 2, 3), (8, 13, 18)):
        assert result['ok'] and result['final']['a']['sword_intent'] == intent
        assert result['final']['a']['def'] == defense and result['final']['a']['qi'] == 29


def test_dragon_effect_uses_the_observed_enabled_switch():
    from test_baijia_combat import simulate
    simulate(3001, ['decrease_atk'], [dict(decrease_atk=0), dict(decrease_atk=1)])
    simulate(3001, ['decrease_atk'], [dict(decrease_atk=0), dict(decrease_atk=0)], disabled=True)


def test_round_eight_pity_and_cat_round_ten():
    pity = describe(14022)
    assert pity['effect']['pool_additions'] == [dict(card_id=10000090, count=6)]
    assert pity['effect']['automatic_pool_draw_after_round'] == 8
    assert pity['effect']['pity_cultivation_cost'] == 1
    assert describe(7009)['timing'] == dict(gift='round', round=10)


def test_twin_engraving_repeats_level_one_and_pays_qi_once():
    states = []
    for cid in (1000019, 1010019, 1000029):
        state = scene([card(cid)], native_baijia_grid_5009=0); state['a']['qi'] = 2
        states.append(state)
    for result, damage in zip(simulate_scenarios(states, timeout=30), (32, 36, 9)):
        assert result['ok'] and result['damage_to_hp']['b'] == damage
        assert result['final']['a']['qi'] == 0 and result['qi_waits']['a'] == 0


def test_foundation_spirit_sword_gift_charges_once():
    before = dict(round=6, realm=2, cultivation=10, mechanisms=[23003], hand=[], board=[],
                  completed_grants=['23003:card:1000007'], processed_events=[])
    after = apply(23003, before, 'breakthrough')
    assert after['cultivation'] == 9 and [c['card_id'] for c in after['hand']] == [1000019]
    assert apply(23003, after, 'round_start')['last_mechanism_action'] == 'hold'


def test_mortal_body_only_adds_future_swap_when_realm_one_is_deployed():
    states = [scene([card(cid)], native_baijia_23086=1) for cid in (1000001, 1000026)]
    for result, expected in zip(simulate_scenarios(states, timeout=30), (1, 0)):
        assert result['ok']
        assert result['final']['a'].get('native_postbattle_rewards', {}).get('swap_chances', 0) == expected


@pytest.mark.parametrize('rank', [0, 1, 2])
def test_softheart_and_changed_ordinary_cards_each_have_exact_values(rank):
    ids = [1000096, 141, 152, 130, 413, 144, 272, 277]
    states = []
    for base in ids:
        cards = [card(base + 10000 * rank)]
        if base == 1000096: cards.append(card(1000001))
        state = scene(cards, cloud_sword_chain_count=1)
        state['a'].update(qi=5, star_power=4)
        states.append(state)
    results = simulate_scenarios(states, timeout=30)
    assert len(results) == len(ids) and all(result['ok'] for result in results)
    soft, starry, galaxy, explosion, burn, crash, recovery, bones = results
    assert soft['final']['a']['max_hp'] == 120 + 10 * rank
    assert soft['final']['a']['hp'] == 52 + rank
    assert starry['final']['a']['def'] == (14, 20, 26)[rank]
    assert galaxy['final']['a']['hp'] == 81 and galaxy['final']['a']['max_hp'] == 131
    assert explosion['damage_to_hp']['b'] == (26, 30, 34)[rank]
    assert explosion['final']['a']['star_power'] == 2
    assert burn['damage_to_hp']['b'] == (30, 42, 54)[rank]
    assert crash['damage_to_hp']['b'] == (13, 18, 23)[rank]
    assert crash['final']['a']['hp'] == (51, 54, 57)[rank]
    assert recovery['final']['a']['qi'] == 7 + rank
    assert bones['final']['a']['hp'] == (55, 60, 65)[rank]


def test_starry_sky_has_no_combo_defense_without_a_cloud_chain():
    state = scene([card(141)], cloud_sword_chain_count=0); state['a']['qi'] = 5
    result = simulate_scenarios([state], timeout=30)[0]
    assert result['ok'] and result['final']['a']['def'] == 4


def test_updated_fate_restrictions_timing_and_pool_numbers():
    rows = catalog()['rows']
    assert rows['17043']['is_available'] is False
    assert rows['17045']['is_available'] is True and rows['17045']['include_characters'] == [2000005]
    from baijia_transform import describe as transformation
    assert transformation(17036)['timing'] == dict(grant_round=4, active_unlock_round=14)
    from baijia_catalog import summarize
    own = dict(ok=True, ids=[17036], counters={'17036': 0}, temp_datas={})
    assert summarize(own, round=13)['rows'][0]['ready'] is False
    assert summarize(own, round=14)['rows'][0]['ready'] is True
    assert describe(17003)['effect']['pool_additions'] == [dict(card_id=421, count=4)]
    assert describe(17003)['timing'] == dict(gift='round', round=12)
    assert describe(17078)['effect']['pool_additions'] == [dict(card_id=189, count=8)]
    assert describe(17078)['effect']['automatic_pool_draw_after_round'] == 12
    assert describe(17079)['effect']['pool_additions'] == [dict(card_id=4000097, count=8), dict(card_id=190, count=8)]
    assert describe(17101)['effect']['pool_additions'] == [dict(card_id=421, count=3)]
    assert describe(17101)['timing'] == dict(gift='round', round=12)
    assert describe(17101)['cost']['cultivation_per_grant'] == 1


def test_first_pool_skips_route_to_the_exact_suanni_pools():
    stages = catalog()['npc_stages']
    assert stages['8']['name'] == '九节' and stages['8']['specialSkip'] == 25
    assert stages['16']['name'] == '丹青客' and stages['16']['specialSkip'] == 24
    assert stages['24']['name'] == stages['25']['name'] == '狻猊'
    from baijia_offer_value import skip_income
    assert skip_income([dict(id=8)]) == skip_income([dict(id=16)]) == 0
    assert skip_income([dict(id=24)]) == 3 and skip_income([dict(id=25)]) == 5


@pytest.mark.parametrize('rank', [0, 1, 2])
def test_five_elements_announcement_conflict_is_not_accepted(rank):
    from card_level_catalog import native_card
    cid = 7000107 + 10000 * rank
    face = native_card(cid)
    resolved = CardResolver().resolve(dict(face, native_card_id=cid))
    assert f'每剩余1灵气多{rank + 2}攻' in face['description']
    assert resolved['custom_effects']['factor'] == rank + 3
