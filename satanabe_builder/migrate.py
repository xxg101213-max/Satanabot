"""Migração conservadora de mudanças em JSON: BASE_ANTIGA -> PATCH_ANTIGO -> BASE_NOVA."""
from __future__ import annotations
import copy
import json
from dataclasses import dataclass

MISSING = object()

@dataclass
class Change:
    path: tuple
    before: object
    after: object


def changes(base, modified, path=()):
    if base == modified:
        return []
    if isinstance(base,dict) and isinstance(modified,dict):
        output=[]
        for k in sorted(base.keys() | modified.keys()):
            if k not in base:
                output.append(Change(path+(k,),MISSING,modified[k]))
            elif k not in modified:
                output.append(Change(path+(k,),base[k],MISSING))
            else:
                output += changes(base[k],modified[k],path+(k,))
        return output
    return [Change(path,base,modified)]


def at_path(obj,path):
    cur=obj
    for k in path:
        if not isinstance(cur,dict) or k not in cur:
            return MISSING
        cur=cur[k]
    return cur


def put_path(obj,path,value):
    if not path:
        return copy.deepcopy(value)
    cur=obj
    for k in path[:-1]:
        if k not in cur or not isinstance(cur[k],dict):
            raise ValueError('Caminho intermediário não existe')
        cur=cur[k]
    if value is MISSING:
        cur.pop(path[-1],None)
    else:
        cur[path[-1]]=copy.deepcopy(value)
    return obj


def migrate_json(old_original:bytes, old_modified:bytes, new_original:bytes):
    base=json.loads(old_original.decode('utf-8'))
    mod=json.loads(old_modified.decode('utf-8'))
    dest=json.loads(new_original.decode('utf-8'))
    result=copy.deepcopy(dest)
    applied=[]
    conflicts=[]
    for change in changes(base,mod):
        existing=at_path(dest,change.path)
        label='/'.join(map(str,change.path)) or '<raiz>'
        if (existing is MISSING and change.before is MISSING) or (existing is not MISSING and change.before is not MISSING and existing==change.before):
            try:
                result=put_path(result,change.path,change.after)
                applied.append(label)
            except (ValueError,KeyError) as ex:
                conflicts.append({'path':label,'reason':str(ex)})
        elif (existing is MISSING and change.after is MISSING) or (existing is not MISSING and change.after is not MISSING and existing == change.after):
            applied.append(label + ' (já presente)')
        else:
            conflicts.append({'path':label,'reason':'A versão nova alterou este campo; precisa de revisão.'})
    return json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'), {'changes':len(changes(base,mod)),'applied':applied,'conflicts':conflicts}
