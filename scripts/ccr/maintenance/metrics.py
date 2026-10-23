#!/usr/bin/env python3
"""Record supplied per-phase counters and summarize disjoint runs without token estimates."""
import argparse
import json
import math
from pathlib import Path
import sys


TOKEN_FIELDS = ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens')
USAGE_FIELDS = TOKEN_FIELDS + ('credits', 'cost', 'currency')
COUNTERS = ('sessions', 'tool_calls', 'repeated_reads', 'tool_output_chars')


def normalize_usage(raw=None):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or set(raw) - set(USAGE_FIELDS):
        raise ValueError('usage requires the normalized fields documented in measurements.md')
    result = {field: raw.get(field) for field in USAGE_FIELDS}
    for field in TOKEN_FIELDS:
        value = result[field]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(field + ' must be a nonnegative integer or null')
    for field in ('credits', 'cost'):
        value = result[field]
        if value is None:
            continue
        try:
            finite = math.isfinite(value) if type(value) in (int, float) else False
        except OverflowError:
            finite = False
        if not finite or value < 0:
            raise ValueError(field + ' must be a finite nonnegative number or null')
    if result['currency'] is not None and (not isinstance(result['currency'], str) or not result['currency'].strip()):
        raise ValueError('currency must be explicit text or null')
    if result['cost'] is not None and result['currency'] is None:
        raise ValueError('measured cost needs an explicit currency')
    for subset, total in (('cached_input_tokens', 'input_tokens'), ('reasoning_tokens', 'output_tokens')):
        if result[subset] is not None and result[total] is not None and result[subset] > result[total]:
            raise ValueError(subset + ' cannot exceed ' + total)
    incoming, outgoing, cached = result['input_tokens'], result['output_tokens'], result['cached_input_tokens']
    result['total_tokens'] = incoming + outgoing if incoming is not None and outgoing is not None else None
    result['uncached_input_tokens'] = incoming - cached if incoming is not None and cached is not None else None
    return result


def summarize(runs):
    if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
        raise ValueError('expected run objects')
    normalized = []
    for run in runs:
        raw = run.get('usage')
        if raw is not None and not isinstance(raw, dict):
            raise ValueError('invalid usage object')
        if isinstance(raw, dict) and set(raw) - set(USAGE_FIELDS) - {'total_tokens', 'uncached_input_tokens'}:
            raise ValueError('unknown usage fields')
        normalized.append(normalize_usage({field: raw.get(field) for field in USAGE_FIELDS} if raw is not None else None))
    result = {'runs': len(runs)}
    for field in TOKEN_FIELDS + ('total_tokens', 'uncached_input_tokens', 'credits'):
        known = [usage[field] for usage in normalized if usage[field] is not None]
        missing = len(runs) - len(known)
        result[field] = {'total': sum(known) if runs and not missing else None,
                         'known_subtotal': sum(known) if known else None, 'unknown_runs': missing}
    currencies = {}
    missing_cost = 0
    for usage in normalized:
        if usage['cost'] is None:
            missing_cost += 1
        else:
            currency = usage['currency']
            currencies[currency] = currencies.get(currency, 0) + usage['cost']
    result['cost_by_currency'] = currencies
    result['cost_unknown_runs'] = missing_cost
    for field in COUNTERS:
        known = []
        for run in runs:
            value = run.get(field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('invalid ' + field)
            if value is not None:
                known.append(value)
        missing = len(runs) - len(known)
        result[field] = {'total': sum(known) if runs and not missing else None,
                         'known_subtotal': sum(known) if known else None, 'unknown_runs': missing}
    return result
