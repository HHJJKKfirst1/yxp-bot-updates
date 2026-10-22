"""Conservative public-source monitor: compile data, never announcement code."""
import json,re,hashlib,urllib.request,time
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from cloud_rules_contract import *

NEWS='https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=1948800&count=5&maxlength=0&feeds=steam_community_announcements'
WIKI='https://sharpobject.github.io/yxp_wiki/zh/cards/'
ALIASES={9:'Spirit Cat Chaos Sword',1000102:'Unrestrained Sword - Crimson Sky',1000103:'Giant Elephant Spirit Sword',
 1000108:'Thousand Blades Sword Formation',7000112:'Wood Spirit - Spreading Branches',7000113:'Fire Spirit - Burn to Ashes',
 7000114:'Earth Spirit - Chasing Dust Step',4000104:'Astral Move - Connect',10000109:'Shura Mystic Qi Slash',
 10000108:'Nether Spirit Blood Shadow Step',28:'Ultimate Hexagram Base',29:'Fury Thunder',214:'Jade Scroll of Yin Symbol',
 381:'Spirit Feather',382:'Cyclone Palm'}
SLOTS={9:0,1000102:3,1000103:0,7000112:1,7000113:2,7000114:2,28:0,381:2,382:2}


def notice_hash(notice):
    # Steam maxlength=0 includes BBCode while shortened feeds strip it.
    # Formatting alone is not an edited balance announcement.
    content=re.sub(r'\[/?[^]]+\]|<[^>]*>','',notice['contents'])
    return hashlib.sha256((plain(notice['title'])+'\n'+plain(content)).encode('utf8')).hexdigest()


def read_url(url):
    request=urllib.request.Request(url,headers={'User-Agent':'YxpPublicRulesMonitor/1'})
    with urllib.request.urlopen(request,timeout=12) as response:
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise RuleRejected('source_too_large')
    return raw


class WikiFaces(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.rows=[];self.row=None;self.in_effect=False;self.in_level=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);classes=(attrs.get('class') or '').split()
        if tag=='article' and 'level-card' in classes:self.row=dict(description='',level=None,native_id=None)
        if self.row is not None:
            if tag=='img' and 'level-card-art' in classes:
                match=re.match(r'(\d+)_',attrs.get('data-card-key',''))
                if match:self.row['native_id']=int(match[1])
            if tag=='strong':self.in_level=True
            if tag=='p':self.in_effect=True
            if tag=='br' and self.in_effect:self.row['description']+='\n'
    def handle_data(self,text):
        if self.row is not None:
            if self.in_effect:self.row['description']+=text
            if self.in_level:
                match=re.search(r'(?:等级|Level)\s*(\d+)',text)
                if match:self.row['level']=int(match[1])
    def handle_endtag(self,tag):
        if tag=='p':self.in_effect=False
        if tag=='strong':self.in_level=False
        if tag=='article' and self.row is not None:self.rows.append(self.row);self.row=None


def observations_for_page(base,registry,reader):
    parser=WikiFaces();parser.feed(reader(WIKI+str(base)+'.html').decode('utf8'))
    rows=[]
    for item in parser.rows:
        ref=registry['faces'].get(str(item['native_id']))
        if not ref:continue
        if item['level'] is None:item['level']=ref['level']
        rows.append({**item,'name':ref['name']})
    expected={x['native_id'] for x in registry['faces'].values() if x['base_id']==base}
    if {x['native_id'] for x in rows}!=expected:raise RuleRejected('wiki_family_incomplete:'+str(base))
    return rows


def replace_number(text,index,value):
    text=re.sub(r'<[^>]*>','',text);matches=list(re.finditer(r'\d+',text))
    m=matches[index];return text[:m.start()]+str(value)+text[m.end():]


def reviewed_notice_observations(notice,pack,registry):
    """Recheck a reviewed balance section and its exact native executable faces.

    An announcement's outfit/body edits do not change an audited card effect.
    A changed balance section, source, native identity, cost or parameter never
    inherits this receipt. It remains pending for independent review.
    """
    try:
        receipts=json.loads(Path(__file__).with_name('reviewed_notices.json').read_text('utf8'))
        receipt=receipts['notices'].get(notice.get('gid'))
    except (OSError,ValueError,KeyError,TypeError):return None
    if receipt is None:return None
    def pending(reason):
        return [],[dict(gid=notice.get('gid'),reason=reason,source=notice.get('url'))]
    if notice.get('url')!=receipt['source']:return pending('reviewed_notice_source_changed')
    content=notice.get('contents','')
    headings=list(re.finditer(r'\[h([1-6])\](.*?)\[/h\1\]',content,re.I|re.S))
    titles=lambda h:plain(re.sub(r'\[/?[^]]+\]|<[^>]*>','',h[2]))
    matches=[i for i,h in enumerate(headings) if titles(h)=='BalanceAdjustments']
    if len(matches)!=1:return pending('reviewed_balance_changed')
    index=matches[0];heading=headings[index]
    end=headings[index+1].start() if index+1<len(headings) else len(content)
    section=content[heading.end():end]
    normalized=plain(re.sub(r'\[/?[^]]+\]|<[^>]*>','',section))
    if hashlib.sha256(normalized.encode('utf8')).hexdigest()!=receipt['balance_sha256']:
        return pending('reviewed_balance_changed')
    outside=re.sub(r'\[/?[^]]+\]|<[^>]*>','',content[:heading.start()]+content[end:])
    if any(name in outside for name in ALIASES.values()):
        return pending('card_change_outside_reviewed_balance')
    try:
        if pack['engine_contract']!=receipt['engine_contract']:raise RuleRejected('engine_changed')
        validate_pack(pack,registry)
        if len(receipt['faces'])!=30:raise RuleRejected('receipt_incomplete')
        rows=[]
        for cid,digest in receipt['faces'].items():
            row=pack['cards'][cid]
            if checksum({k:v for k,v in row.items() if k!='description'})!=digest:
                raise RuleRejected('native_face_changed')
            rows.append(dict(row))
    except (RuleRejected,KeyError,TypeError):return pending('reviewed_native_faces_changed')
    return rows,[]


def notice_observations(notice,pack,registry):
    reviewed=reviewed_notice_observations(notice,pack,registry)
    if reviewed is not None:return reviewed
    bounded=re.sub(r'\[/p\]|\[/\*\]|</p>', '\n',notice.get('contents',''),flags=re.I)
    content=re.sub(r'\[/?[^]]+\]|<[^>]*>','',bounded)
    positions=sorted((content.find(name),base,name) for base,name in ALIASES.items() if name in content)
    observations=[];pending=[]
    for index,(start,base,name) in enumerate(positions):
        end=positions[index+1][0] if index+1<len(positions) else len(content)
        paragraph=content.find('\n',start)
        if paragraph!=-1:end=min(end,paragraph)
        section=content[start:end].split('4. Bug Fixes',1)[0]
        if base not in SLOTS:
            pending.append(dict(base_id=base,reason='notice_needs_specific_adapter',source=notice['url']));continue
        slot=SLOTS[base]
        if base==1000102:
            # Printed ATK and the maximum ATK-increase stacks are distinct
            # executable parameters (slots 3 and 2). Bind the property as well
            # as the native identity; an arbitrary number is insufficient.
            change=r'(\d+(?:/\d+)*)\s*(?:→|->|\bto\b)\s*\+?(\d+(?:/\d+)*)'
            body=section[len(name):].strip()
            if re.fullmatch(r':\s*Max ATK increase\s+'+change+r'\s+stacks\.?',body,re.I):slot=2
            elif not re.fullmatch(r':\s*\d+(?:/\d+)*\s+ATK\s*(?:→|->|\bto\b)\s*\d+(?:/\d+)*\s+ATK\.?',body,re.I):
                pending.append(dict(base_id=base,reason='notice_needs_specific_adapter',source=notice['url']));continue
        changes=list(re.finditer(r'(\d+(?:/\d+)*)\s*(?:ATK\s*)?(?:[×x]\s*\d+\s*)?(?:→|->|\bto\b)\s*\+?(\d+(?:/\d+)*)',section))
        if len(changes)!=1:
            pending.append(dict(base_id=base,reason='ambiguous_official_number_change',source=notice['url']));continue
        old,new=([int(x) for x in changes[0][i].split('/')] for i in (1,2))
        if len(old) not in (1,3) or len(new) not in (1,3):
            pending.append(dict(base_id=base,reason='ambiguous_rank_change',source=notice['url']));continue
        old=old*3 if len(old)==1 else old;new=new*3 if len(new)==1 else new
        if base==7000113 and re.search(r"Reduce enemy[’']s HP\s*&\s*Max HP by",section):slot=0
        if base==7000114 and re.search(r"\bDef\s*\+",section):slot=0
        for rank in range(1,4):
            if base==9 and re.search(r'Lv\.?\s*2.*?Lv\.?\s*3',section) and rank==1:continue
            cid=str(base+(rank-1)*10000);row=pack['cards'].get(cid)
            if row is None:continue
            current=row['parameters'][slot]
            if current==new[rank-1]:
                observations.append(dict(row));continue
            if current!=old[rank-1]:
                pending.append(dict(native_id=int(cid),reason='official_before_value_mismatch',source=notice['url']));continue
            observations.append({**row,'description':replace_number(row['description'],slot,new[rank-1])})
    return observations,pending


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.part')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8');tmp.replace(path)


def notice_effective_at(item):
    content=re.sub(r'\[/?[^]]+\]|<[^>]*>','',item['contents'])
    if not re.search(r'UTC\s*\+\s*8',content,re.I):return None
    zone=timezone(timedelta(hours=8))
    day=datetime.fromtimestamp(item['date'],zone)
    # Existing hotfix wording binds "today" to the announcement's date.
    hotfix=re.search(r'(\d{1,2}):(\d{2})\s*today\b',content,re.I)
    if hotfix:return day.replace(hour=int(hotfix[1]),minute=int(hotfix[2]),second=0,microsecond=0)
    # Season launches put the absolute date before the clock, e.g.
    # "on October 15 at 11:00(UTC+8)". A clock alone is not sufficient.
    launch=re.search(r'on\s+([A-Za-z]+)\s+(\d{1,2})\s+at\s+(\d{1,2}):(\d{2})\s*\(UTC\s*\+\s*8\)',content,re.I)
    months={name:i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
    if launch and launch[1].title() in months:
        return day.replace(month=months[launch[1].title()],day=int(launch[2]),hour=int(launch[3]),minute=int(launch[4]),second=0,microsecond=0)
    return None


def monitor(folder,*,reader=read_url,now=None):
    folder=Path(folder);public=folder/'public';registry=json.loads((folder/'registry.json').read_text('utf8'))
    manifest=json.loads((public/'manifest.json').read_text('utf8'))
    pack=validate_pack(json.loads((public/manifest['rules']).read_text('utf8')),registry)
    if checksum(pack)!=manifest['sha256']:raise RuleRejected('published_baseline_hash_mismatch')
    now=now or datetime.now(timezone.utc);pending=[];proposed=deepcopy(pack);changed=[];source_errors=[]
    try:news=json.loads(reader(NEWS).decode('utf8'))['appnews']['newsitems']
    except Exception as error:
        news=[];source_errors.append(dict(source='official_steam_news',error=str(error)))
    accepted=manifest.get('accepted_notices',{})
    new_notices=[]
    for item in sorted(news,key=lambda x:x['date']):
        digest=notice_hash(item)
        if accepted.get(item['gid'])==digest:continue
        if item['date']<manifest.get('baseline_notice_date',0) and item['gid'] not in accepted:continue
        # The announcement's own effective time is binding, not detection time.
        try:effective=notice_effective_at(item)
        except (ValueError,TypeError,OverflowError):effective=None
        if effective is None:
            pending.append(dict(gid=item['gid'],reason='official_effective_time_needs_review',source=item['url']));continue
        if effective>now:
            pending.append(dict(gid=item['gid'],reason='announced_rule_not_effective_yet',source=item['url']));continue
        observed,unhandled=notice_observations(item,proposed,registry)
        proposed,rejected,updated=apply_observations(proposed,registry,observed,official=True)
        pending.extend(unhandled+rejected);changed.extend(updated)
        if not observed and not unhandled:
            pending.append(dict(gid=item['gid'],reason='new_announcement_requires_review',source=item['url']))
        new_notices.append(dict(gid=item['gid'],title=item['title'],url=item['url'],date=item['date'],sha256=digest))
        if observed and not unhandled and not rejected:accepted[item['gid']]=digest
    bases=sorted({row['base_id'] for row in pack['cards'].values()})
    def read(base):
        try:return observations_for_page(base,registry,reader),None
        except Exception as error:return [],dict(base_id=base,error=str(error))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for observed,error in pool.map(read,bases):
            if error:source_errors.append(error);continue
            # A notice-confirmed value must not be undone by a delayed Wiki.
            observed=[r for r in observed if r['native_id'] not in changed]
            proposed,rejected,updated=apply_observations(proposed,registry,observed)
            pending.extend(rejected);changed.extend(updated)
    pending=list({json.dumps(x,sort_keys=True):x for x in pending}.values())
    if changed:
        proposed.update(serial=pack['serial']+1,revision=now.astimezone(timezone(timedelta(hours=8))).strftime('%Y.%m.%d')+'.'+str(pack['serial']+1),
            effective_at=now.isoformat())
        validate_pack(proposed,registry)
        name='rules/'+proposed['revision']+'.json';atomic(public/name,proposed)
        manifest.update(serial=proposed['serial'],revision=proposed['revision'],rules=name,sha256=checksum(proposed),
            engine_contract=proposed['engine_contract'])
        if proposed['engine_contract']==ADAPTER_CONTRACT:
            manifest['minimum_assistant_version']=ADAPTER_MINIMUM_VERSION
        elif proposed['engine_contract']==OCT15_CONTRACT:
            manifest['minimum_assistant_version']=OCT15_MINIMUM_VERSION
    # Record metadata only, not copied article bodies or user/game logs.
    status=dict(checked_at=now.isoformat(),notices=new_notices,pending=pending,source_errors=source_errors,
        changed_native_ids=sorted(set(changed)),state='verified' if not source_errors else 'partial_source_failure')
    try:previous=json.loads((public/'monitor_status.json').read_text('utf8'))
    except (OSError,ValueError):previous={}
    compare=lambda x:{k:v for k,v in x.items() if k!='checked_at'}
    heartbeat=previous.get('checked_at','')[:13]!=now.isoformat()[:13]
    metadata=dict(monitor_state=status['state'],source_errors=source_errors,
        supported_faces=len(proposed['cards']))
    metadata_changed=any(manifest.get(key)!=value for key,value in metadata.items())
    if changed or compare(previous)!=compare(status) or heartbeat or metadata_changed:
        atomic(public/'monitor_status.json',status)
        manifest.update(pending=pending,source_checked_at=now.isoformat(),accepted_notices=accepted,**metadata)
        atomic(public/'manifest.json',manifest)
    return status


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default='.')
    args=parser.parse_args();print(json.dumps(monitor(args.folder),ensure_ascii=False))
