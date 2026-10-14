"""Gera ZIP de workspace para importação no aplicativo 3105, NÃO pacote .3105 criptografado."""
from pathlib import PurePosixPath
import io
import json
import re
import zipfile
from .core import safe_name

def workspace_zip(filename: str, payload:bytes, bundle_id:str)->bytes:
    if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}',bundle_id):
        raise ValueError('Bundle ID inválido. Ex.: com.exemplo.aplicativo')
    p=PurePosixPath(filename.replace('\\','/'))
    if not safe_name(str(p)):
        raise ValueError('Caminho inválido')
    segments=p.parts
    if 'Documents' not in segments:
        raise ValueError('Arquivo deve ter caminho relativo contendo Documents/')
    idx=segments.index('Documents')
    target=PurePosixPath('Application')/bundle_id/PurePosixPath(*segments[idx:])
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('settings.json',json.dumps({'schemaVersion':1,'fields':[]}))
        z.writestr(str(target),payload)
    return out.getvalue()
