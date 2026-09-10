"""Frozen response extraction and item flags, applied identically to both rounds.
No API calls. Unknown or out-of-range choices remain None; never force failure.
"""
import re

def extract(record):
    text=record['raw_response'].strip()
    choices=record['choices']
    patterns=[(r'FINAL\s*:\s*([A-Z])','strict_final','full'),
              (r'FINAL\s*:\s*([A-Z])\s*$','explicit_final_after_reasoning','search'),
              (r'\\boxed\{([A-Z])\}\$?\s*$','explicit_boxed','boxed')]
    for pattern,rule,mode in patterns:
        m=re.fullmatch(pattern,text,re.I) if mode=='full' else re.search(pattern,text,0 if mode=='boxed' else re.I)
        if m:
            index=ord(m[1].upper())-65
            return (choices[index],rule) if 0<=index<len(choices) else (None,'invalid_option')
    m=re.fullmatch(r'([A-Z])\.\s*(.+)',text,re.S)
    if m:
        index=ord(m[1])-65
        if 0<=index<len(choices) and m[2].strip()==choices[index]:
            return choices[index],'explicit_option_and_matching_text'
    return None,'undetermined'

def score(record):
    if record['status']!='ok':
        return None,'api_error'
    prediction,rule=extract(record)
    return (prediction==record['expected_answer'] if prediction is not None else None),rule

def flags(records):
    result={}
    for record in records:
        if record['status']!='ok':
            continue
        item=result.setdefault(record['id'],{})
        condition=record['condition']
        if condition in item:
            raise ValueError('Duplicate successful item/condition')
        correct,rule=score(record)
        item[condition]=correct
    return {i:[v.get('original'),v.get('change'),v.get('preserve'),
               not v['text_only'] if v.get('text_only') is not None else None] for i,v in result.items()}
