"""Data-only numerical templates shared by the publisher and the client."""
import hashlib,json,re,unicodedata
from datetime import datetime,timezone

SCHEMA=1
PRODUCT='yxp-verified-numeric-rules'
ENGINE_CONTRACT='numeric-templates-1'
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
    if not isinstance(text,str) or len(text)>4096 or shape(text)!=shape(reference['description']):
        raise RuleRejected('effect_template_changed')
    original,current=numbers(reference['description']),numbers(text)
    if len(original)!=len(current):raise RuleRejected('number_slot_count_changed')
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
    return {k:reference[k] for k in ('native_id','name','level','base_id','simulator_id','template','qi_cost','hp_cost')} | dict(description=text,parameters=current)


def validate_pack(pack,registry):
    if not isinstance(pack,dict) or pack.get('schema')!=SCHEMA or pack.get('product')!=PRODUCT or pack.get('engine_contract')!=ENGINE_CONTRACT:
        raise RuleRejected('rules_schema_incompatible')
    if not isinstance(pack.get('serial'),int) or isinstance(pack['serial'],bool) or pack['serial']<1:raise RuleRejected('serial_invalid')
    try:
        effective=datetime.fromisoformat(pack['effective_at'].replace('Z','+00:00'))
        if effective.tzinfo is None:raise ValueError()
    except (KeyError,TypeError,ValueError):raise RuleRejected('effective_time_invalid')
    cards=pack.get('cards')
    if not isinstance(cards,dict) or set(cards)!=set(registry['faces']):raise RuleRejected('complete_registry_required')
    for cid,row in cards.items():
        if not isinstance(row,dict):raise RuleRejected('card_record_invalid')
        if (not isinstance(row.get('parameters'),list) or
            any(type(x) is not int for x in row['parameters'])):raise RuleRejected('parameter_type_invalid')
        compiled=compile_face(registry['faces'][cid],row)
        if compiled!=row:raise RuleRejected('parameters_do_not_match_effect')
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
        # A Wiki that still shows the pre-Oct.8 face cannot revert a verified
        # official change. Known retired descriptions are not new evidence.
        retired=list(ref.get('retired_effects',()))+list(map(plain,pack.get('accepted_history',{}).get(cid,())))
        if not official and plain(row.get('description')) in retired:continue
        try:compiled=compile_face(ref,row)
        except RuleRejected as error:
            pending.append(dict(native_id=int(cid),reason=str(error)));continue
        if compiled!=result['cards'][cid]:
            history=result.setdefault('accepted_history',{}).setdefault(cid,[])
            history.append(result['cards'][cid]['description'])
            result['accepted_history'][cid]=list(dict.fromkeys(history))[-8:]
            result['cards'][cid]=compiled;changed.append(int(cid))
    try:validate_pack(result,registry)
    except RuleRejected as error:
        return deepcopy(pack),pending+[dict(reason=str(error))],[]
    return result,pending,changed
