"""3105PATCH v3 exporter based on upstream GPLv3 PatchPackageCodec.swift.
Only targets Application scope. Reopening provides cryptographic roundtrip validation;
real device patch application must still be tested in the 3105 app.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac, sha256
import os
import plistlib
import re
from uuid import uuid4
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .patch3105 import MAGIC, decode, Patch3105Error

MAX_SIZE=256*1024*1024

def create3105(files: list[tuple[str,str,bytes]], name='Satanabe Patch', password: str|None=None) -> bytes:
    """files = list[(bundle_id, path relative to Documents container, data)]."""
    if not 1<=len(files)<=4000:
        raise Patch3105Error('Pacote precisa conter pelo menos um arquivo')
    package_id=str(uuid4()).upper()
    rule_list=[]
    digests={}
    all_bundles=[]
    seen=set()
    total=0
    for bundle,relative,data in files:
        if not isinstance(bundle,str) or len(bundle)>255 or not re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+',bundle) or any(p.startswith('-') or p.endswith('-') for p in bundle.split('.')):
            raise Patch3105Error('Identificador do aplicativo inválido')
        if not isinstance(relative,str) or len(relative.encode('utf-8'))>4096 or not relative or relative.startswith('/') or '\\' in relative or ':' in relative or any(p in ('','.','..') for p in relative.split('/')):
            raise Patch3105Error('Caminho de destino inválido')
        if not isinstance(data,bytes): raise Patch3105Error('Substituição não binária')
        if (bundle,relative) in seen: raise Patch3105Error('Arquivo duplicado')
        seen.add((bundle,relative))
        if bundle not in all_bundles:all_bundles.append(bundle)
        total += len(data)
        if total>MAX_SIZE:raise Patch3105Error('Tamanho de pacote excedido')
        rid=str(uuid4()).upper()
        rule_list.append(dict(id=rid,bundleID=bundle,relativePath=relative,replacementFilename=relative.rsplit('/',1)[-1],replacementData=data))
        digests[rid]=sha256(data).digest()
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    project=dict(id=package_id,name=name[:120],author='Satanabe AI Builder',isPrivate=False,
                 createdAt=now,updatedAt=now,bundleIdentifiers=all_bundles,directories=[],rules=rule_list)
    contentkey=os.urandom(32)
    payload=plistlib.dumps({'project':project,'replacementDigests':digests},fmt=plistlib.FMT_BINARY)
    nonce=os.urandom(12)
    ciphertext=nonce+AESGCM(contentkey).encrypt(nonce,payload,f'3105PATCH/v3/payload/{package_id}'.encode())
    protected=bool(password)
    salt=iterations=wrapped=publickey=keyaadver=None
    if protected:
        if len(password.encode())>1024:raise Patch3105Error('Senha excessivamente longa')
        salt=os.urandom(16);iterations=250000
        wrappingkey=pbkdf2_hmac('sha256',password.encode(),salt,iterations,32)
        nonce=os.urandom(12)
        wrapped=nonce+AESGCM(wrappingkey).encrypt(nonce,contentkey,f'3105PATCH/v3/key/{package_id}'.encode())
        keyaadver=3
    else:publickey=contentkey
    envelope=dict(schemaVersion=3,keyAADVersion=keyaadver,packageID=package_id,
                  isPasswordProtected=protected,kdfSalt=salt,kdfIterations=iterations,
                  wrappedContentKey=wrapped,publicContentKey=publickey,
                  keyFingerprint=sha256(contentkey).digest(),encryptedPayload=ciphertext)
    envelope={key:value for key,value in envelope.items() if value is not None}
    binary=MAGIC+plistlib.dumps(envelope,fmt=plistlib.FMT_BINARY)
    # Check authentication, routing and bytes before returning. Never silently publish an invalid build.
    reopened=decode(binary,password)
    expected=[(f'Application/{b}/{p}',d) for b,p,d in files]
    if [(e['name'],e['data']) for e in reopened['files']]!=expected:
        raise Patch3105Error('Verificação de pacote falhou')
    return binary
