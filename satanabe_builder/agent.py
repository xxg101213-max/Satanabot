"""DeepSeek/OpenRouter or Groq tool-calling agent with bounded read/build tools.
No shell, arbitrary code execution, file path traversal, or autonomous binary patching.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Callable
from .brain import _request_json, openrouter_headers, openrouter_model, OPENROUTER_URL
from .managed import inspect_managed, ManagedError
from .overlay import build_overlay, checked_config
from .core import inspect

BASE='https://api.groq.com/openai/v1/chat/completions'
SYSTEM=('Você é o agente técnico Satanabe AI Builder. Nunca invente implementações ou offsets. '
        'Use ferramentas disponíveis para inspecionar e compilar quando solicitado. '
        'A compilação do Overlay cria apenas uma biblioteca geométrica: não torna ESP operacional em jogos terceiros. '
        'Não peça credenciais; nunca invente testes realizados. Responda em português brasileiro.')
TOOLS=[
 {'type':'function','function':{'name':'inspect_assembly','description':'Inspeciona o Assembly gerenciado enviado pelo usuário; retorna classes e métodos quando o formato permite.','parameters':{'type':'object','properties':{},'additionalProperties':False}}},
 {'type':'function','function':{'name':'inspect_file','description':'Detecta o formato e hashes do arquivo enviado.','parameters':{'type':'object','properties':{},'additionalProperties':False}}},
 {'type':'function','function':{'name':'compile_overlay','description':'Compila um componente DLL geométrico para FOV, Box, Line Tracer, Skeleton e Nome, SEM integração no jogo.','parameters':{'type':'object','properties':{},'additionalProperties':False}}}
]

def _reply(messages:list, model:str):
    key=os.getenv('GROQ_API_KEY','').strip()
    if not key: raise RuntimeError('Configure GROQ_API_KEY')
    body={'model':model,'messages':messages,'tools':TOOLS,'tool_choice':'auto','temperature':0.1,'max_completion_tokens':1800,'stream':False}
    try:
        response=_request_json(BASE,{'Authorization':f'Bearer {key}'},body)
    except RuntimeError as first:
        if model!='openai/gpt-oss-20b' and ('HTTP 403' in str(first) or 'HTTP 404' in str(first)):
            body['model']='openai/gpt-oss-20b'
            response=_request_json(BASE,{'Authorization':f'Bearer {key}'},body)
        else:raise
    return response['choices'][0]['message']

def _reply_openrouter(messages:list, model:str):
    body={'model':model,'messages':messages,'tools':TOOLS,'tool_choice':'auto',
          'temperature':0.1,'max_tokens':1800,'stream':False}
    response=_request_json(OPENROUTER_URL,openrouter_headers(),body)
    choices=response.get('choices') or []
    if not choices:
        raise RuntimeError('OpenRouter retornou resposta vazia')
    return choices[0]['message']


def run_agent(request: str, path:Path|None, controls:dict|None=None,
              api:Callable|None=None, mode:str='auto') -> dict:
    """Run max 3 model decisions, with explicit allowlisted local tools only.
    Caller decides whether compiled bytes may be delivered; no silent filesystem writes.
    """
    if len(request)>3000: request=request[:3000]
    outputs=[]
    decisions=[]
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':request}]
    # DeepSeek is preferred unless the user specifically selects Groq.
    groq_ready=bool(os.getenv('GROQ_API_KEY','').strip())
    deepseek_ready=bool(os.getenv('OPENROUTER_API_KEY','').strip())
    if not api and not groq_ready and not deepseek_ready:
        raise RuntimeError('Configure GROQ_API_KEY ou OPENROUTER_API_KEY')
    if mode=='groq':
        provider='groq' if groq_ready else 'deepseek'
    else:
        provider='deepseek' if deepseek_ready else 'groq'
    model=openrouter_model() if provider=='deepseek' else os.getenv('GROQ_MODEL','openai/gpt-oss-20b')
    for _ in range(3):
        call=api or (_reply_openrouter if provider=='deepseek' else _reply)
        try:
            msg=call(messages,model)
        except RuntimeError as first:
            # Select one fallback; do not retry with the same failed provider.
            backup='groq' if provider=='deepseek' else 'deepseek'
            if api or not (groq_ready if backup=='groq' else deepseek_ready):
                raise
            provider=backup
            model=openrouter_model() if provider=='deepseek' else os.getenv('GROQ_MODEL','openai/gpt-oss-20b')
            call=_reply_openrouter if provider=='deepseek' else _reply
            msg=call(messages,model)
            decisions.append({'fallback_from':str(first)[:160],'provider':provider})

        calls=msg.get('tool_calls') or []
        if not calls:
            return {'response':msg.get('content') or '', 'tools':decisions,'files':outputs,'provider':provider}
        messages.append({'role':'assistant','content':msg.get('content') or None,'tool_calls':calls})
        for c in calls[:3]:
            name=c.get('function',{}).get('name','')
            result={}
            try:
                if name=='inspect_file':
                    if not path:raise ValueError('Anexe um arquivo antes')
                    parsed=inspect(path)
                    result={'kind':parsed.kind,'sha256':parsed.sha256,'entries':[{'path':e.name,'signature':e.signature} for e in parsed.entries[:10]]}
                elif name=='inspect_assembly':
                    if not path:raise ValueError('Anexe o Assembly antes')
                    result=inspect_managed(path)
                elif name=='compile_overlay':
                    output=build_overlay(controls or {})
                    result={key:value for key,value in output.items() if key not in ('binary','source')}
                    if output['success']:
                        outputs.append(('SatanabeOverlay.dll',output['binary']))
                        outputs.append(('SatanabeOverlay.cs',output['source'].encode()))
                else:
                    result={'error':'Ferramenta não autorizada'}
            except (ValueError,OSError,ManagedError,RuntimeError) as exc:
                result={'error':str(exc)[:450]}
            decisions.append({'tool':name,'result':result})
            messages.append({'role':'tool','tool_call_id':c['id'],'content':json.dumps(result,ensure_ascii=False,default=str)[:3200]})
    return {'response':'Limite de passos da IA atingido. Relatório das ferramentas disponível.', 'tools':decisions,'files':outputs,'provider':provider}
