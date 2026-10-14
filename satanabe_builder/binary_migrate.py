"""Conservative three-way byte delta: does not infer offsets or run untrusted code.

Supports only unique, byte-identical anchors surrounding small size-preserving
changes. If any hunk is uncertain, refuses to generate a modified file.
This is NOT semantic IL2CPP adaptation nor a test of game functionality.
"""
from __future__ import annotations
from hashlib import sha256

class UnsafeMigration(ValueError):
    pass


def migrate_anchored(old_original: bytes, old_modified: bytes, new_original: bytes) -> tuple[bytes,dict]:
    if len(old_original) != len(old_modified):
        raise UnsafeMigration('O patch alterou o tamanho do binário; não é seguro transportar os bytes.')
    if not 64 <= len(old_original) <= 19_000_000 or len(new_original) > 19_000_000:
        raise UnsafeMigration('Tamanho de arquivo fora do intervalo seguro.')
    hunks=[]
    start=None
    changed=0
    for i, (a,b) in enumerate(zip(old_original,old_modified)):
        if a != b:
            changed += 1
            if start is None:
                start=i
        elif start is not None:
            hunks.append((start,i))
            start=None
    if start is not None:
        hunks.append((start,len(old_original)))
    if not hunks:
        raise UnsafeMigration('Não há diferenças entre o original antigo e o patch antigo.')
    if len(hunks)>64 or changed>4096 or changed*100>len(old_original):
        raise UnsafeMigration('Muitas diferenças binárias para uma migração automática conservadora.')
    out=bytearray(new_original)
    placements=[]
    # Match anchors in the pristine new build, not against a progressively edited buffer.
    for start,end in hunks:
        if end-start>128:
            raise UnsafeMigration('Alteração binária individual muito extensa.')
        left=old_original[max(0,start-64):start]
        right=old_original[end:min(len(old_original),end+64)]
        if len(left)<16 or len(right)<16:
            raise UnsafeMigration('Alteração próxima ao início ou fim: faltam âncoras.')
        search=left + old_original[start:end] + right
        loc=new_original.find(search)
        if loc<0:
            raise UnsafeMigration('O padrão antigo não existe na versão nova; offsets podem ter mudado.')
        if new_original.find(search,loc+1)>=0:
            raise UnsafeMigration('Padrão duplicado no Assembly novo; correspondência ambígua.')
        dest=loc+len(left)
        if any(dest < prev_end and dest+(end-start)>prev_start for prev_start,prev_end in placements):
            raise UnsafeMigration('Alterações sobrepostas na versão nova.')
        placements.append((dest,dest+(end-start)))
        out[dest:dest+(end-start)]=old_modified[start:end]
    report={'status':'MIGRACAO_BINARIA_POR_ANCORAS','hunks':len(hunks),'bytes_alterados':changed,
            'old_original_sha256':sha256(old_original).hexdigest(),
            'old_modified_sha256':sha256(old_modified).hexdigest(),
            'new_original_sha256':sha256(new_original).hexdigest(),
            'output_sha256':sha256(out).hexdigest(),
            'validation':'Padrões de bytes e âncoras únicas verificados; funcionamento no jogo NÃO testado.',
            'requires_runtime_test':True}
    return bytes(out), report
