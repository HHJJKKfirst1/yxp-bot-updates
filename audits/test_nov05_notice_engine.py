"""Independent literal checks for the Nov 5 announcement and live adapters.

The published announcement and separately extracted native build 26449625
provide these expected numbers. Recognition alone never proves random effects.
"""
from pathlib import Path
import os
import sys

import pytest

ROOT = Path(os.environ['YXP_AUDIT_ENGINE_ROOT']).resolve()
sys.path.insert(0, str(ROOT / 'joint_repair_artifacts'))
sys.path.append(str(ROOT))


def test_changed_npc_rounds_and_second_pool_skip_are_bound_to_current_native_data():
    from baijia_catalog import catalog
    c = catalog()
    stages = c['npc_stages']
    assert stages['2']['maxRound'] == 6
    assert stages['5']['minRound'] == 7
    assert stages['7']['maxRound'] == 13
    assert stages['10']['maxRound'] == 13
    assert stages['14']['specialSkip'] == 24
    assert stages['14']['skipGotReplaceChance'] == 3
    assert stages['21']['minRound'] == 7 and stages['21']['maxRound'] == 13
    assert stages['21']['weight'] == 80 and stages['22']['weight'] == 30
    assert c['skip_options']['24']['skip_got_replace_chance'] == 3
    assert c['skip_options']['25']['skip_got_replace_chance'] == 5


@pytest.mark.parametrize('sid,key,cost,bonus', [
    (22001, 'refine_destiny', 2, 4),
    (22002, 'refine_rerolls', 2, 2),
    (22003, 'refine_max_hp', 5, 2),
])
def test_recycling_scroll_cost_and_each_of_seven_refinements(sid, key, cost, bonus):
    from baijia_refinement_runtime import describe
    effect = describe(sid)
    assert effect['cost']['destiny'] == cost
    assert effect['effect'][key] == bonus
    assert effect['limits']['bonus_refinements'] == 7
    assert effect['limits']['each_physical_debit_consumes_one_bonus'] is True


@pytest.mark.parametrize('sid', [10001, 10003])
def test_real_book_choice_costs_ten_and_retry_is_due_next_round(sid):
    from baijia_books import describe
    spec = describe(sid)
    assert spec['cost']['destiny_on_real_choice'] == 10
    assert spec['cost']['retry'] == 0
    assert spec['cost']['retry_449_swaps_due_next_round'] == 1
    assert spec['timing']['retry_restore'] == 'next_round_native_counter_zero_and_ready'


def test_retry_clause_is_bound_to_native_card_449_not_similar_tianyan_retry():
    from baijia_books import describe
    from card_level_catalog import native_card
    card = native_card(449)
    assert '下轮' in card['description'] and '1换牌' in card['description']
    assert describe(10003)['cost']['retry_99000006_swaps_due_next_round'] == 'unverified'


@pytest.mark.parametrize('sid', [4022, 4033])
def test_both_rhymes_grant_their_aura_at_round_thirteen_with_cost(sid):
    from baijia_offer_mechanisms import describe
    spec = describe(sid)
    assert spec['timing']['reward_round'] == 13
    assert spec['effect']['round_reward'] == {'cultivation': -2, 'cards': [46]}


def test_nonmatching_element_fate_grants_two_swaps():
    from baijia_offer_mechanisms import describe
    assert describe(4013)['effect']['nonmatching_fate_rerolls'] == 2


def test_sword_self_unity_keeps_selection_gain_and_refine_bonus_distinct():
    from baijia_auxiliary_passives import describe
    effect = describe(23044)['effect']
    assert effect['selection_rerolls'] == 3
    assert effect['rerolls'] == 1 and effect['all_grades_same_family'] is True


def test_snow_practice_four_round_cooldown_uses_the_observed_last_round():
    from baijia_catalog import summarize
    def observed(now):
        return summarize(dict(ok=True, ids=[23084], counters={'23084': 7},
                              temp_datas={}), round=now)['rows'][0]
    assert observed(10)['ready_round'] == 11 and observed(10)['ready'] is False
    assert observed(11)['ready'] is True


def test_secret_seal_shift_has_native_golden_core_realm_gate():
    from baijia_transform import describe
    spec = describe(23057)
    assert spec['timing']['minimum_realm'] == 3
    assert spec['effect']['transform'] == 'matching_level_one_secret_seal'
    assert spec['limits']['uses'] == 1


@pytest.mark.parametrize('sid,round_no,pool_count,pool_card', [
    (14022, 6, 6, 10000090),
    (17021, 8, 6, 139),
    (17028, 12, 6, 413),
    (17095, 12, 6, 419),
])
def test_updated_draw_pool_grants_keep_native_count_and_paid_pity(sid, round_no, pool_count, pool_card):
    from baijia_preparation_events import describe
    spec = describe(sid)
    assert spec['effect']['pool_additions'] == [{'card_id': pool_card, 'count': pool_count}]
    assert spec['effect']['automatic_pool_draw_after_round'] == round_no
    assert spec['effect']['pity_cultivation_cost'] == 1
    assert spec['effect']['pity_native_pool_debit'] == 1


@pytest.mark.parametrize('sid,round_no,orbs', [(17006, 12, 4), (17007, 10, 2), (17098, 12, 4)])
def test_updated_gift_and_fusion_orb_are_due_at_native_round(sid, round_no, orbs):
    from baijia_preparation_events import describe
    spec = describe(sid)
    assert spec['timing'] == {'gift': 'round', 'round': round_no}
    assert spec['cost']['cultivation_per_grant'] == 1
    assert spec['effect']['grant_count'] == 1
    assert spec['effect']['pool_additions'] == [{'card_id': 421, 'count': orbs}]


def test_back_to_void_grants_two_then_preserves_reversible_hand_forms():
    from baijia_transform import describe
    spec = describe(7044)
    assert spec['cost']['automatic_grant_cultivation'] == 2
    assert spec['effect']['grant_count'] == 2 and spec['effect']['grant_card_id'] == 216
    assert spec['timing']['grant_round'] == 12
    assert spec['timing']['active_unlock_round'] == 11
    assert spec['effect']['reversible'] is True and spec['effect']['preserve_grade'] is True


@pytest.mark.parametrize('cid,gain', [(400, 10), (10400, 16), (20400, 22)])
def test_cloudstill_current_max_hp_and_hp_in_the_actual_engine(cid, gain):
    from test_hidden_effects_v339 import card, scene
    from yisim_damage_simulator import simulate_scenario
    result = simulate_scenario(scene([card(cid)]), timeout=10)
    assert result['ok'], result
    assert result['final']['a']['max_hp'] == 100 + gain
    assert result['final']['a']['hp'] == 50 + gain


def test_battle_experience_can_only_use_observed_one_opportunity():
    from baijia_catalog import summarize
    from baijia_active_effects import describe
    spec = describe(23052)
    assert spec['limits']['uses'] == 1 and spec['limits']['unlock_after_wins'] == 6
    def item(counter):
        return summarize(dict(ok=True, ids=[23052], counters={'23052': counter},
                              temp_datas={}), round=12)['rows'][0]
    assert item(-1)['ready'] is True and item(-1)['remaining'] == 1
    assert item(0)['ready'] is False and item(0)['remaining'] == 0


@pytest.mark.parametrize('cid,qi_gain,def_per_element', [(295, 2, 2), (10295, 3, 4), (20295, 4, 6)])
def test_older_mirage_five_elements_activates_both_neighbors_only_when_they_generate(cid, qi_gain, def_per_element):
    from test_hidden_effects_v339 import card, scene
    from yisim_damage_simulator import simulate_scenarios
    # Wood generates fire. Metal and wood do not generate each other.
    scenarios = []
    for following in (7000009, 7000001):
        s = scene([card(cid), card(following)] + [card(0)] * 5 + [card(7000003)])
        s['a']['qi'] = 10
        scenarios.append(s)
    generating, not_generating = simulate_scenarios(scenarios, timeout=10)
    assert generating['ok'] and not_generating['ok']
    assert generating['final']['a']['def'] == 2 * def_per_element
    assert generating['final']['a']['qi'] == 10 + qi_gain + 1  # chained fire seal
    assert not_generating['final']['a']['def'] == 0
    assert not_generating['final']['a']['qi'] == 10 + qi_gain


@pytest.mark.parametrize('cid,damage', [(297, 12), (10297, 18), (20297, 24)])
def test_older_mirage_rakshasa_uses_both_attacks_at_each_current_grade(cid, damage):
    from test_hidden_effects_v339 import card, scene
    from yisim_damage_simulator import simulate_scenario
    s = scene([card(cid)])
    s['a']['qi'] = 10
    result = simulate_scenario(s, timeout=10)
    assert result['ok'] and result['damage_to_hp']['b'] == damage
    assert result['final']['a']['qi'] == 11
