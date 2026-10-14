"""Inspeção de arquivos locais e workspaces 3105 sem contornar criptografia."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
import zipfile

LIMIT_BYTES = 256 * 1024 * 1024
LIMIT_FILES = 4000

@dataclass
class Entry:
    name: str
    category: str
    size: int
    sha256: str | None = None
    signature: str = "unknown"

@dataclass
class Inspection:
    kind: str
    file: str
    sha256: str
    entries: list[Entry]
    note: str

    def json(self):
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def category_for(name: str) -> str:
    lower = name.lower().replace('\\','/')
    base = PurePosixPath(lower).name
    if '/avatar/' in lower or 'assetindexer' in base:
        return 'avatar'
    if 'cache_res' in base or '/gameassetbundles/' in lower:
        return 'cache_res'
    if 'assembly-csharp' in base or base.startswith('assembly'):
        return 'assembly'
    return 'outro'


def sniff(data: bytes, filename: str) -> str:
    if data.startswith((b'MZ',)):
        return 'PE/.NET potencial (requer parser)'
    if data.startswith((b'UnityFS',b'UnityRaw',b'UnityWeb')):
        return 'Unity AssetBundle'
    if data.startswith((b'PK\x03\x04',)):
        return 'ZIP'
    if data.lstrip().startswith((b'{', b'[')):
        try:
            json.loads(data.decode('utf-8'))
            return 'JSON'
        except (UnicodeError,ValueError):
            pass
    if filename.endswith('.bytes'):
        return 'bytes de formato não identificado'
    return 'binário ou texto não identificado'


def safe_name(name: str):
    q = PurePosixPath(name.replace('\\','/'))
    return bool(name) and not q.is_absolute() and '..' not in q.parts and not name.startswith('~') and ':' not in q.parts[0]


def inspect(path: Path) -> Inspection:
    digest = file_hash(path)
    if zipfile.is_zipfile(path):
        entries = []
        total = 0
        with zipfile.ZipFile(path) as z:
            infos = [i for i in z.infolist() if not i.is_dir()]
            if len(infos) > LIMIT_FILES:
                return Inspection('rejeitado',path.name,digest,[], 'Arquivo contém entradas demais.')
            for info in infos:
                total += info.file_size
                if not safe_name(info.filename) or total > LIMIT_BYTES or info.file_size > LIMIT_BYTES:
                    return Inspection('rejeitado',path.name,digest,[], 'ZIP inseguro ou acima do limite de expansão.')
                with z.open(info) as stream:
                    first = stream.read(min(info.file_size, 65536))
                entries.append(Entry(info.filename, category_for(info.filename), info.file_size, signature=sniff(first,info.filename.lower())))
        found = [e for e in entries if e.category!='outro']
        return Inspection('workspace_zip',path.name,digest,entries,
                          f'{len(found)} arquivo(s) reconhecido(s). ZIP/workspace não é necessariamente pacote .3105 válido.')
    with path.open('rb') as f:
        prefix=f.read(65536)
    category=category_for(path.name)
    if path.suffix.lower()=='.3105':
        return Inspection('3105_opaco',path.name,digest,[],
                          'Pacote .3105 não legível como ZIP. Pode estar criptografado: exporte o workspace pelo aplicativo 3105. Nenhum conteúdo interno foi presumido.')
    return Inspection('arquivo_solto',path.name,digest,
                      [Entry(path.name,category,path.stat().st_size,digest,sniff(prefix,path.name.lower()))],
                      'Classificação por caminho/nome e assinatura; não comprova semântica interna.')


def read_entry(path: Path, entry_name: str) -> bytes:
    if not zipfile.is_zipfile(path):
        return path.read_bytes()
    if not safe_name(entry_name):
        raise ValueError('Caminho inválido')
    with zipfile.ZipFile(path) as z:
        info=z.getinfo(entry_name)
        if info.file_size>LIMIT_BYTES:
            raise ValueError('Arquivo muito grande')
        return z.read(info)
