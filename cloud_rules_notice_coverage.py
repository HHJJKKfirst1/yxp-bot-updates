"""Data-only inventory of ALL balance entries, independent of numeric coverage.

An accepted numeric notice is never a receipt for an unregistered Immortal Fate.
Mechanism receipts are local reviewed data bound to the complete balance section
and the exact item. No module name, expression, or remote code is evaluated.
"""
import hashlib
import html
import re
from copy import deepcopy

from cloud_rules_contract import checksum, plain


HEADING = re.compile(r'\[h([1-6])\](.*?)\[/h\1\]|<h([1-6])[^>]*>(.*?)</h\3>', re.I | re.S)
DIGEST = re.compile(r'[a-f0-9]{64}')
VERSION = re.compile(r'\d+\.\d+\.\d+')
LABELS = {'immortalfateadjustments', 'relatedcardadjustments', 'cardadjustments'}


def text(value):
    value = re.sub(r'\[/?[^]]+\]|<[^>]*>', '', value)
    return ' '.join(html.unescape(value).split())


def heading(match):
    return int(match[1] or match[3]), text(match[2] if match[1] else match[4])


def paragraphs(value):
    value = re.sub(r'\[/?p\]|</?p\b[^>]*>|\[br\]|<br\s*/?>', '\n', value, flags=re.I)
    return [clean for line in value.splitlines() if (clean := text(line))]


def balance_parts(notice):
    """Keep child headings; stop only at a sibling/parent of Balance.

    Minimal historical numeric notices have no heading. Their body is still
    inventoried, with only the explicit update-clock introduction ignored.
    """
    content = notice.get('contents', '')
    headings = list(HEADING.finditer(content))
    balances = [i for i, h in enumerate(headings)
                if plain(re.sub(r'^\s*\d+[.、)]\s*', '', heading(h)[1])).lower()
                in ('balanceadjustment', 'balanceadjustments', '平衡调整')]
    if len(balances) > 1:
        return '', [], 'balance_heading_ambiguous'
    if not balances:
        if headings:
            return '', [], 'balance_section_requires_review'
        return content, [], None
    index = balances[0]
    level, title = heading(headings[index])
    end = next((h.start() for h in headings[index + 1:] if heading(h)[0] <= level), len(content))
    return content[headings[index].end():end], [(level, title)], None


def balance_inventory(notice):
    section, initial, error = balance_parts(notice)
    result = dict(gid=str(notice.get('gid', '')), source=notice.get('url'),
                  title=notice.get('title', ''), date=notice.get('date', 0),
                  scope='all_balance_items', balance_sha256=hashlib.sha256(plain(text(section)).encode('utf8')).hexdigest(),
                  items=[], extraction_error=error)
    if error:
        return result
    path = list(initial)
    pseudo = []

    def add(block):
        nonlocal pseudo
        lines = paragraphs(block)
        if not lines:
            return
        if len(lines) == 1 and plain(lines[0]).lower() in LABELS:
            pseudo = [lines[0]]
            return
        # The official notice puts this owner inside the preceding list.
        if lines == ['The old man in white']:
            pseudo = lines
            return
        if not initial and len(lines) == 1 and re.fullmatch(
                r'(?:Hi everyone[,!]?|(?:Yi Xian will be |Update at ).*?\(UTC\s*\+\s*8\)\.?)', lines[0], re.I):
            return
        description = '\n'.join(lines)
        contexts = [h[1] for h in path] + pseudo
        category = 'unknown'
        for context in contexts:
            if 'immortal fate' in context.lower(): category = 'immortal_fate'
            elif 'card adjustment' in context.lower(): category = 'card'
        if re.match(r'(?:New Immortal Fate:|Immortal Fate Pool\b|The following Immortal Fates\b|For all Immortal Fates\b)',
                    description, re.I): category = 'immortal_fate'
        targets = []
        if len(lines) > 1 and re.match(r'The following Immortal Fates\b', lines[0], re.I):
            targets = [name.strip(' .') for name in ', '.join(lines[1:]).split(',') if name.strip(' .')]
        if not targets:
            label = re.sub(r'^.*?\bnew Immortal Fate:\s*', '', lines[0], flags=re.I)
            pieces = label.split(':')
            count = 2 if pieces[0] in ('Dream', 'Ultimate', 'Mirage') else 1
            targets = [':'.join(pieces[:count])[:180]]
        for target in targets:
            digest = checksum(dict(section=contexts, target=target, text=plain(description)))
            result['items'].append(dict(item_id='%03d-%s' % (len(result['items']) + 1, digest[:16]),
                item_sha256=digest, section=contexts, target=target, kind=category, text=description))

    def chunk(value):
        # Steam also permits [*] lists without explicit [/*] terminators.
        parts = re.split(r'(\[\*\]|\[/\*\]|<li\b[^>]*>|</li>)', value, flags=re.I)
        inside = False
        buffer = ''
        def emit(block, grouped):
            if grouped: add(block)
            else:
                for line in paragraphs(block): add(line)
        for part in parts:
            if re.fullmatch(r'\[\*\]|<li\b[^>]*>', part, re.I):
                emit(buffer, inside); buffer = ''; inside = True
            elif re.fullmatch(r'\[/\*\]|</li>', part, re.I):
                emit(buffer, inside); buffer = ''; inside = False
            else: buffer += part
        emit(buffer, inside)

    offset = 0
    for h in HEADING.finditer(section):
        chunk(section[offset:h.start()])
        level, title = heading(h)
        path = [(n, name) for n, name in path if n < level] + [(level, title)]
        pseudo = []
        offset = h.end()
    chunk(section[offset:])
    if not result['items']:
        result['extraction_error'] = 'balance_entries_require_review'
    return result


def _review(receipts, inventory, item):
    """A reviewed mechanism declares its required client, not installed support."""
    if not receipts:
        return None, None
    if not isinstance(receipts, dict) or receipts.get('schema') != 1 or not isinstance(receipts.get('notices'), dict):
        return None, 'coverage_ledger_invalid'
    receipt = receipts['notices'].get(inventory['gid'])
    if receipt is None:
        return None, None
    if (not isinstance(receipt, dict) or receipt.get('source') != inventory['source'] or
            receipt.get('balance_sha256') != inventory['balance_sha256']):
        return None, 'coverage_review_source_or_balance_changed'
    reviews = receipt.get('items')
    if not isinstance(reviews, dict):
        return None, 'coverage_ledger_invalid'
    review = reviews.get(item['item_id'])
    if review is None:
        return None, None
    if not isinstance(review, dict) or review.get('item_sha256') != item['item_sha256']:
        return None, 'coverage_review_item_changed'
    required = {'item_sha256', 'kind', 'engine_contract', 'minimum_assistant_version', 'evidence_sha256'}
    if (set(review) != required or review.get('kind') not in ('mechanism', 'activity_excluded') or
            not isinstance(review.get('engine_contract'), str) or
            not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}', review['engine_contract']) or
            not isinstance(review.get('minimum_assistant_version'), str) or
            not VERSION.fullmatch(review['minimum_assistant_version']) or
            not isinstance(review.get('evidence_sha256'), list) or not review['evidence_sha256'] or
            not all(isinstance(x, str) and DIGEST.fullmatch(x) for x in review['evidence_sha256'])):
        return None, 'coverage_review_invalid'
    return deepcopy(review), None


def notice_coverage(notice, *, numeric_check, numeric_contract, numeric_minimum,
                    legacy_numeric_receipt=False, receipts=None):
    inventory = balance_inventory(notice)
    report = {k: v for k, v in inventory.items() if k not in ('items', 'extraction_error')}
    report.update(items=[], pending=[], reviewed_count=0, excluded_count=0)
    if inventory['extraction_error']:
        report['pending'].append(dict(gid=inventory['gid'], source=inventory['source'],
                                      reason=inventory['extraction_error']))
    for item in inventory['items']:
        row = {k: v for k, v in item.items() if k != 'text'}
        review, error = _review(receipts, inventory, item)
        if review is not None:
            row.update(state='excluded_activity' if review['kind'] == 'activity_excluded' else 'reviewed',
                       review=review)
            if review['kind'] == 'activity_excluded': report['excluded_count'] += 1
            else: report['reviewed_count'] += 1
        else:
            numeric = None if item['kind'] == 'immortal_fate' else numeric_check(item['text'])
            # Legacy receipts bind the ENTIRE exact card section and all its
            # native faces. They cannot cover a newly added fate subsection.
            if not error and item['kind'] != 'immortal_fate' and (numeric or legacy_numeric_receipt):
                row.update(state='reviewed_numeric', engine_contract=numeric_contract,
                    minimum_assistant_version=numeric_minimum,
                    receipt_scope='audited_registered_card_balance' if legacy_numeric_receipt else 'exact_numeric_sentence')
                if numeric: row['native_ids'] = numeric
                report['reviewed_count'] += 1
            else:
                row.update(state='pending_review', reason=error or 'announcement_item_requires_review')
                report['pending'].append(dict(gid=inventory['gid'], source=inventory['source'],
                    item_id=item['item_id'], item_sha256=item['item_sha256'],
                    target=item['target'], section=item['section'], reason=row['reason']))
        report['items'].append(row)
    report.update(item_count=len(report['items']), pending_count=len(report['pending']),
                  state='pending_review' if report['pending'] else 'reviewed',
                  fully_reviewed=not report['pending'])
    return report


def coverage_summary(notices, *, source_available=True):
    latest = max(notices, key=lambda gid: (notices[gid].get('date', 0), gid)) if notices else None
    required = notices.get(latest, {})
    return dict(schema=1, scope='all_balance_items', notices=notices, latest_notice_gid=latest,
        latest_item_count=required.get('item_count', 0), latest_reviewed_count=required.get('reviewed_count', 0),
        latest_excluded_count=required.get('excluded_count', 0), latest_pending_count=required.get('pending_count', 0),
        state=('source_unavailable' if not source_available else
               'pending_review' if any(n.get('pending') for n in notices.values()) else
               'reviewed' if notices else 'no_announcements'),
        source_available=source_available,
        support_claim='review_receipts_require_matching_client_contract')
