"""Gerador de especificações de interface; não injeta ESP nem altera lógica de jogos."""
import json
import re
from datetime import datetime,timezone
COLORS={'vermelho':'#FF4040','vermelha':'#FF4040','red':'#FF4040','azul':'#3295FF','blue':'#3295FF','verde':'#22CC66','green':'#22CC66','branco':'#FFFFFF','white':'#FFFFFF','preto':'#000000','amarelo':'#FFD442','roxo':'#A855F7','rosa':'#FF69B4','ciano':'#00DFFF'}
FEATURES={'fov':['fov','campo de visao'], 'line_tracer':['line tracer','linha tracer','linhas'], 'box':['box','caixa'], 'skeleton':['skeleton','esqueleto'], 'name':['nome','name']}

def color_for(text:str, feature:str):
    # Lê cor após o nome da função, quando informada; não atribui cores ao acaso.
    match=re.search(re.escape(feature)+r'\s*(?:\+|:|=|cor|color|na cor|em)?\s*(#[0-9a-fA-F]{6}|'+ '|'.join(COLORS)+r')\b',text,re.I)
    if match:
        return COLORS.get(match.group(1).lower(),match.group(1).upper())
    return '#FFFFFF'

def make_plan(prompt:str):
    lower=prompt.lower()
    is_esp=('esp' in lower or any(x in lower for x in ('line tracer','skeleton','fov')))
    types=[]
    for name, aliases in FEATURES.items():
        mention=next((a for a in aliases if a in lower),None)
        if mention:
            types.append({'feature':name,'enabled':True,'color':color_for(lower,mention) if name!='name' else None})
    if is_esp and not types:
        types=[{'feature':k,'enabled':False,'color':'#FFFFFF' if k!='name' else None} for k in FEATURES]
    if is_esp:
        task='esp_ui_specification'
        prerequisite='Integração em renderizador/painel autorizado; esta receita somente descreve interface.'
    elif any(x in lower for x in ['bala magica','bala mágica','hitbox','cabeca','cabeça','pescoço','avatar']):
        task='asset_analysis_request'
        prerequisite='Requer formato decodificado e modelo do jogo; nenhuma alteração de hitbox será inventada.'
    else:
        task='unclassified_request'
        prerequisite='Requer especificação e adaptador de arquivo antes de executar.'
    return {'schema_version':1,'created_utc':datetime.now(timezone.utc).isoformat(),
            'kind':task,'request':prompt[:2000],'controls':types,
            'requires_implementation':True,'require_validation':True,
            'note':prerequisite}

def pretty_plan(prompt:str)->bytes:
    return json.dumps(make_plan(prompt),ensure_ascii=False,indent=2).encode('utf-8')
