"""Data-only numerical templates shared by the publisher and the client."""
import hashlib,json,re,unicodedata
from datetime import datetime,timezone

SCHEMA=1
PRODUCT='yxp-verified-numeric-rules'
ENGINE_CONTRACT='numeric-templates-1'
ADAPTER_CONTRACT='numeric-templates-2'
OCT15_CONTRACT='numeric-templates-3'
OCT29_CONTRACT='numeric-templates-4'
SUPPORTED_ENGINE_CONTRACTS=frozenset((ENGINE_CONTRACT,ADAPTER_CONTRACT,OCT15_CONTRACT,OCT29_CONTRACT))
ADAPTER_MINIMUM_VERSION='1.1.299'
OCT15_MINIMUM_VERSION='1.1.329'
OCT29_MINIMUM_VERSION='1.1.356'
MAX_BYTES=2*1024*1024


class RuleRejected(ValueError):pass


def plain(text):
    value=unicodedata.normalize('NFKC',re.sub(r'<[^>]*>','',str(text)))
    value=value.replace('\\n','\n').replace('\\r','')
    value=value.translate(str.maketrans({'～':'~','“':'"','”':'"','「':'"','」':'"'}))
    return re.sub(r'[\s\[\]]','',value)


def numbers(text):return [int(x) for x in re.findall(r'\d+',plain(text))]
def shape(text):return re.sub(r'\d+','<n>',plain(text))
def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8')
def checksum(value):return hashlib.sha256(encoded(value)).hexdigest()
def utcnow():return datetime.now(timezone.utc).isoformat()


def compile_face(reference,observed):
    if (type(observed.get('native_id')) is not int or type(observed.get('level')) is not int or
        not isinstance(observed.get('name'),str)):
        raise RuleRejected('native_identity_type_invalid')
    for key in ('native_id','name','level'):
        if reference.get(key)!=observed.get(key):raise RuleRejected('exact_native_identity_changed')
    text=observed.get('description')
    if not isinstance(text,str) or len(text)>4096:
        raise RuleRejected('effect_template_changed')
    variant=None
    if shape(text)!=shape(reference['description']):
        variant=next((v for v in reference.get('effect_variants',())
            if shape(text)==shape(v['description'])),None)
        if variant is None:raise RuleRejected('effect_template_changed')
    original,current=numbers(reference['description']),numbers(text)
    if variant is not None and 'parameter_prefix' in variant:
        prefix=variant['parameter_prefix']
        if not isinstance(prefix,list) or any(type(n)is not int for n in prefix):
            raise RuleRejected('adapter_parameter_prefix_invalid')
        current=prefix+current
    if len(original)!=len(current):raise RuleRejected('number_slot_count_changed')
    if variant is not None:
        order=variant.get('parameter_order',list(range(len(original))))
        if (any(type(i)is not int for i in order) or sorted(order)!=list(range(len(original)))):
            raise RuleRejected('adapter_parameter_order_invalid')
        current=[current[i] for i in order]
    mutable=set(reference['mutable_slots'])
    for i,(old,new) in enumerate(zip(original,current)):
        if i not in mutable and old!=new:raise RuleRejected('unsupported_number_slot')
        if not 0<=new<=10000:raise RuleRejected('numeric_value_out_of_range')
        if i in reference.get('positive_slots',()) and new<1:raise RuleRejected('zero_divisor')
        if i in reference.get('loop_slots',()) and new>32:raise RuleRejected('action_count_out_of_range')
    # Wiki omits reliable play costs. A descriptor refresh must never invent
    # a new printed cost; those need an independently verified cost contract.
    for key in ('qi_cost','hp_cost'):
        value=observed.get(key,reference[key])
        if type(value) is not int or value!=reference[key]:raise RuleRejected('cost_contract_required')
    result={k:reference[k] for k in ('native_id','name','level','base_id','simulator_id','template','qi_cost','hp_cost')}
    if variant is not None:result['template']=variant.get('template',reference['template'])
    return result | dict(description=text,parameters=current)


def same_executable_face(first,second):
    """Wording may differ only after the exact native template compiled equally."""
    return {k:v for k,v in first.items() if k!='description'}=={k:v for k,v in second.items() if k!='description'}


def validate_pack(pack,registry):
    if not isinstance(pack,dict) or pack.get('schema')!=SCHEMA or pack.get('product')!=PRODUCT or pack.get('engine_contract')not in SUPPORTED_ENGINE_CONTRACTS:
        raise RuleRejected('rules_schema_incompatible')
    if not isinstance(pack.get('serial'),int) or isinstance(pack['serial'],bool) or pack['serial']<1:raise RuleRejected('serial_invalid')
    try:
        effective=datetime.fromisoformat(pack['effective_at'].replace('Z','+00:00'))
        if effective.tzinfo is None:raise ValueError()
    except (KeyError,TypeError,ValueError):raise RuleRejected('effective_time_invalid')
    cards=pack.get('cards')
    expected=set(registry['faces'])
    if pack['engine_contract']not in (OCT15_CONTRACT,OCT29_CONTRACT):
        expected=set(registry.get('legacy_native_ids',expected))
    if not isinstance(cards,dict) or set(cards)!=expected:raise RuleRejected('complete_registry_required')
    for cid,row in cards.items():
        if not isinstance(row,dict):raise RuleRejected('card_record_invalid')
        if (not isinstance(row.get('parameters'),list) or
            any(type(x) is not int for x in row['parameters'])):raise RuleRejected('parameter_type_invalid')
        compiled=compile_face(registry['faces'][cid],row)
        if compiled!=row:raise RuleRejected('parameters_do_not_match_effect')
        if (row['template']!=registry['faces'][cid]['template'] or
            shape(row['description'])!=shape(registry['faces'][cid]['description'])) and pack['engine_contract']not in (ADAPTER_CONTRACT,OCT15_CONTRACT,OCT29_CONTRACT):
            raise RuleRejected('engine_template_update_required')
    for group in registry.get('shared_slots',()):
        for slot in group['slots']:
            if len({cards[str(cid)]['parameters'][slot] for cid in group['ids']})!=1:
                raise RuleRejected('rank_dependent_shared_hook_requires_adapter')
    history=pack.get('accepted_history',{})
    if not isinstance(history,dict) or not set(history)<=set(cards):raise RuleRejected('rule_history_invalid')
    for cid,texts in history.items():
        if not isinstance(texts,list) or len(texts)>8:raise RuleRejected('rule_history_invalid')
        for text in texts:
            compile_face(registry['faces'][cid],{**cards[cid],'description':text})
    if pack['engine_contract']==OCT29_CONTRACT:
        # Mechanism updates require a locally reviewed complete registry. No
        # expression, handler name or executable code is downloaded or run.
        fates=pack.get('fates');allowed=registry.get('fates')
        if not isinstance(allowed,dict)or not allowed or not isinstance(fates,dict)or set(fates)!=set(allowed):
            raise RuleRejected('complete_reviewed_fate_registry_required')
        if pack.get('fate_registry_sha256')!=checksum(allowed):raise RuleRejected('fate_registry_hash_mismatch')
        for sid,entry in fates.items():
            ref=allowed[sid]
            if not isinstance(entry,dict)or checksum(entry)!=checksum(ref):raise RuleRejected('unreviewed_fate_mechanism:'+sid)
            if type(entry.get('native',{}).get('id'))is not int or str(entry['native']['id'])!=sid:
                raise RuleRejected('fate_native_identity_mismatch:'+sid)
        mechanism_cards=pack.get('mechanism_cards');allowed_cards=registry.get('mechanism_cards')
        if not isinstance(allowed_cards,dict)or not allowed_cards or not isinstance(mechanism_cards,dict)or set(mechanism_cards)!=set(allowed_cards):
            raise RuleRejected('complete_reviewed_mechanism_card_registry_required')
        if pack.get('mechanism_cards_registry_sha256')!=checksum(allowed_cards):raise RuleRejected('mechanism_card_registry_hash_mismatch')
        for cid,entry in mechanism_cards.items():
            if not isinstance(entry,dict)or checksum(entry)!=checksum(allowed_cards[cid]):raise RuleRejected('unreviewed_card_mechanism:'+cid)
            if type(entry.get('native_id'))is not int or str(entry['native_id'])!=cid:raise RuleRejected('mechanism_card_native_identity_mismatch:'+cid)
    elif any(k in pack for k in ('fates','fate_registry_sha256','mechanism_cards','mechanism_cards_registry_sha256')):
        raise RuleRejected('fate_rules_require_engine_contract_4')
    if len(encoded(pack))>MAX_BYTES:raise RuleRejected('rules_package_too_large')
    return pack


def apply_observations(pack,registry,observations,*,official=False):
    """Return a new data candidate; unsupported observations stay pending."""
    from copy import deepcopy
    result=deepcopy(pack);pending=[];changed=[]
    for row in observations:
        cid=str(row.get('native_id'));ref=registry['faces'].get(cid)
        if not ref:
            pending.append(dict(native_id=row.get('native_id'),reason='unregistered_template'));continue
        if cid not in result['cards']:
            pending.append(dict(native_id=int(cid),reason='engine_template_update_required'));continue
        # A Wiki that still shows the pre-Oct.8 face cannot revert a verified
        # official change. Known retired descriptions are not new evidence.
        retired=list(ref.get('retired_effects',()))+list(map(plain,pack.get('accepted_history',{}).get(cid,())))
        if not official and plain(row.get('description')) in retired:continue
        try:compiled=compile_face(ref,row)
        except RuleRejected as error:
            pending.append(dict(native_id=int(cid),reason=str(error)));continue
        if (not same_executable_face(compiled,result['cards'][cid]) or
            plain(compiled['description'])!=plain(result['cards'][cid]['description'])):
            history=result.setdefault('accepted_history',{}).setdefault(cid,[])
            history.append(result['cards'][cid]['description'])
            result['accepted_history'][cid]=list(dict.fromkeys(history))[-8:]
            result['cards'][cid]=compiled;changed.append(int(cid))
            if compiled['template']!=ref['template'] or shape(compiled['description'])!=shape(ref['description']):
                if result['engine_contract']not in(OCT15_CONTRACT,OCT29_CONTRACT):result['engine_contract']=ADAPTER_CONTRACT
    try:validate_pack(result,registry)
    except RuleRejected as error:
        return deepcopy(pack),pending+[dict(reason=str(error))],[]
    return result,pending,changed
