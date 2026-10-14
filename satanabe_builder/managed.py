"""Adapter for managed .NET only. No assumption that an IL2CPP dump is editable."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

WORKER = Path(os.getenv('ASSEMBLY_WORKER', '/opt/assembly-worker/AssemblyWorker.dll'))

class ManagedError(ValueError):
    pass

def available() -> bool:
    return WORKER.is_file()

def _invoke(argv: list[str], timeout=60) -> dict:
    if not available():
        raise ManagedError('Ferramenta .NET não instalada neste servidor')
    try:
        p = subprocess.run(['dotnet',str(WORKER),*argv], capture_output=True, text=True, timeout=timeout, check=False, env={**os.environ,'DOTNET_CLI_TELEMETRY_OPTOUT':'1'})
    except (OSError, subprocess.TimeoutExpired) as ex:
        raise ManagedError('Não foi possível executar o analisador de Assembly') from ex
    if p.returncode:
        raise ManagedError(p.stderr.strip()[:500] or 'Assembly inválido ou não gerenciado')
    try:
        return json.loads(p.stdout)
    except ValueError:
        raise ManagedError('Resposta inválida do analisador') from None

def inspect_managed(path: Path) -> dict:
    return _invoke(['inspect',str(path)])

def migrate_literals(original: Path, modified: Path, updated: Path, output: Path) -> dict:
    result = _invoke(['migrate',str(original),str(modified),str(updated),str(output)],timeout=100)
    if result.get('applied'):
        inspect_managed(output)  # Assembly roundtrip check, NOT in-game validation.
    return result


def replace_string(source: Path, output: Path, before: str, after: str) -> dict:
    report=_invoke(['replace-string', str(source), str(output), before, after])
    inspect_managed(output)
    return report
