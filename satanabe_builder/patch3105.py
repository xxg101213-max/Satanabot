"""Leitor de pacotes .3105 baseado no formato público PatchPackageCodec.

Implementação Python independente para pacotes 3105PATCH v1-v3.
Não contorna senhas: o pacote protegido exige a senha original.
Fonte da especificação: https://github.com/YangJiiii/3105/blob/main/ThreeOneOSFive/helpers/PatchPackageCodec.swift
"""
from __future__ import annotations

import hashlib
import hmac
import io
import plistlib
from pathlib import PurePosixPath
from uuid import UUID
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

MAGIC = b'3105PATCH\0'
MAX_PACKAGE = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_FILES = 4000

class Patch3105Error(ValueError):
    pass

class PasswordNeeded(Patch3105Error):
    pass


def _uuid(raw: object) -> str:
    try:
        return str(UUID(str(raw))).upper()
    except (ValueError, AttributeError, TypeError):
        raise Patch3105Error('Identificador de pacote inválido') from None


def _envelope(data: bytes) -> tuple[dict, str]:
    if not data.startswith(MAGIC):
        raise Patch3105Error('Cabeçalho 3105PATCH não encontrado')
    if len(data) > MAX_PACKAGE:
        raise Patch3105Error('Pacote acima do limite de análise')
    try:
        obj = plistlib.loads(data[len(MAGIC):])
        if not isinstance(obj, dict):
            raise ValueError('plist')
        version = obj['schemaVersion']
        if type(version) is not int or not 1 <= version <= 3:
            raise Patch3105Error(f'Schema .3105 não suportado: {version}')
        identity = _uuid(obj['packageID'])
        if not isinstance(obj['encryptedPayload'], bytes) or len(obj['encryptedPayload']) < 28:
            raise ValueError('payload')
        if not isinstance(obj['keyFingerprint'], bytes) or len(obj['keyFingerprint']) != 32:
            raise ValueError('fingerprint')
        return obj, identity
    except Patch3105Error:
        raise
    except (KeyError, TypeError, ValueError, plistlib.InvalidFileException):
        raise Patch3105Error('Metadados .3105 inválidos ou danificados') from None


def summary(data: bytes) -> dict:
    obj, identity = _envelope(data)
    return {
        'package_id': identity,
        'schema_version': obj['schemaVersion'],
        'password_protected': obj.get('isPasswordProtected') is True,
    }


def decode(data: bytes, password: str | None = None) -> dict:
    obj, identity = _envelope(data)
    version = obj['schemaVersion']
    protected = obj.get('isPasswordProtected') is True
    try:
        if protected:
            if not password:
                raise PasswordNeeded('O .3105 exige a senha original do pacote')
            salt, iterations, wrapped = obj['kdfSalt'], obj['kdfIterations'], obj['wrappedContentKey']
            if not isinstance(salt, bytes) or len(salt) != 16 or type(iterations) is not int or not 100_000 <= iterations <= 1_000_000:
                raise Patch3105Error('Parâmetros da senha inválidos')
            if not isinstance(wrapped, bytes) or len(wrapped) != 60:
                raise Patch3105Error('Chave protegida inválida')
            key_version = obj.get('keyAADVersion') or version
            if type(key_version) is not int or not 1 <= key_version <= 3:
                raise Patch3105Error('Versão da chave não suportada')
            wrapkey = hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,iterations,32)
            aad = f'3105PATCH/v{key_version}/key/{identity}'.encode()
            contentkey = AESGCM(wrapkey).decrypt(wrapped[:12],wrapped[12:],aad)
        else:
            contentkey = obj['publicContentKey']
            if not isinstance(contentkey, bytes):
                raise Patch3105Error('Chave do pacote não encontrada')
        if len(contentkey) != 32 or not hmac.compare_digest(hashlib.sha256(contentkey).digest(),obj['keyFingerprint']):
            raise Patch3105Error('Integridade da chave inválida')
        cipher = obj['encryptedPayload']
        aad = f'3105PATCH/v{version}/payload/{identity}'.encode()
        payload = plistlib.loads(AESGCM(contentkey).decrypt(cipher[:12],cipher[12:],aad))
        project = payload['project']
        rules = project['rules']
        digests = payload['replacementDigests']
        if not isinstance(rules,list) or len(rules) > MAX_FILES or not isinstance(digests,dict) or len(digests) != len(rules):
            raise Patch3105Error('Lista de arquivos inválida')
        if _uuid(project['id']) != identity:
            raise Patch3105Error('ID do projeto divergente')
        result = []
        seen = set()
        total = 0
        for rule in rules:
            bundle, relative = rule['bundleID'], rule['relativePath']
            if not isinstance(bundle,str) or not isinstance(relative,str):
                raise Patch3105Error('Caminho de destino inválido')
            if len(bundle)>255 or len(bundle.split('.'))<2 or not all(x and x[0]!='-' and x[-1]!='-' and all(c.isascii() and (c.isalnum() or c=='-') for c in x) for x in bundle.split('.')):
                raise Patch3105Error('Bundle ID inválido')
            pp = PurePosixPath(relative)
            if not relative or relative.startswith('/') or '\\' in relative or ':' in relative or '..' in pp.parts or any(x in ('','.') for x in relative.split('/')) or len(relative)>4096:
                raise Patch3105Error('Caminho inseguro no pacote')
            data_bytes = rule['replacementData']
            if not isinstance(data_bytes,bytes):
                raise Patch3105Error('Substituição não binária')
            filename = f'Application/{bundle}/{relative}'
            if filename in seen:
                raise Patch3105Error('Caminhos duplicados no pacote')
            seen.add(filename)
            digest_id = _uuid(rule['id'])
            expected = digests.get(digest_id)
            if not isinstance(expected,bytes) or not hmac.compare_digest(hashlib.sha256(data_bytes).digest(),expected):
                raise Patch3105Error('Hash do arquivo não confere')
            total += len(data_bytes)
            if total > MAX_EXPANDED:
                raise Patch3105Error('Conteúdo expandido acima do limite')
            result.append({'name':filename,'data':data_bytes})
        return {'summary':summary(data),'name':str(project.get('name',''))[:120],'files':result}
    except PasswordNeeded:
        raise
    except InvalidTag:
        raise Patch3105Error('Senha incorreta ou pacote corrompido') from None
    except Patch3105Error:
        raise
    except (KeyError,TypeError,ValueError,OverflowError,plistlib.InvalidFileException):
        raise Patch3105Error('Falha ao validar ou abrir o pacote') from None


def as_workspace_zip(data: bytes, password: str | None = None) -> bytes:
    parsed = decode(data,password)
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for item in parsed['files']:
            z.writestr(item['name'],item['data'])
    return output.getvalue()
