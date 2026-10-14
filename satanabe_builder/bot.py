"""Bot Telegram funcional para inspeção, especificações e migração JSON segura.

Não promete quebrar criptografia .3105, migrar binários opacos nem criar ESP operacional.
"""
from __future__ import annotations
import io
import asyncio
import json
import os
from pathlib import Path, PurePosixPath
from uuid import uuid4
from telegram import Update, InputFile, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from .core import inspect, read_entry, category_for
from .migrate import migrate_json
from .planner import pretty_plan, make_plan
from .brain import explain_request, provider_status, MODES
from .workspace import workspace_zip
from .patch3105 import as_workspace_zip, Patch3105Error
from .managed import inspect_managed, migrate_literals, replace_string, ManagedError, available as managed_available
from .overlay import build_overlay
from .export3105 import create3105
from .agent import run_agent

DATA=Path(os.getenv('DATA_DIR','./runtime')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
ALLOW={int(x) for x in os.getenv('ALLOWED_TELEGRAM_IDS','').split(',') if x.strip().isdigit()}
MAX_TG_BYTES=19_000_000
ESP_FEATURES={'fov':'FOV','line_tracer':'Line Tracer','box':'Box','skeleton':'Skeleton','name':'Nome'}
ESP_COLORS={'r':('#FF4040','Vermelho'),'b':('#3295FF','Azul'),'g':('#22CC66','Verde'),'w':('#FFFFFF','Branco'),'y':('#FFD442','Amarelo'),'p':('#A855F7','Roxo'),'c':('#00DFFF','Ciano')}
MENU=ReplyKeyboardMarkup([['🔄 Atualizar','🔍 Analisar'],['✨ Criar','🤖 Perguntar à IA'],['🧠 Status IA','❌ Cancelar']],resize_keyboard=True)


def user_dir(user_id:int):
    path=DATA/str(user_id)
    path.mkdir(parents=True,exist_ok=True)
    return path


def read_state(uid:int):
    f=user_dir(uid)/'state.json'
    try: return json.loads(f.read_text())
    except (OSError,ValueError): return {}


def state_set(uid:int,state:dict):
    f=user_dir(uid)/'state.json'
    temp=f.with_suffix('.tmp')
    temp.write_text(json.dumps(state,ensure_ascii=False), encoding='utf-8')
    temp.replace(f)



def ai_preferences(uid: int) -> dict:
    f = user_dir(uid) / 'ai_preferences.json'
    try:
        prefs = json.loads(f.read_text(encoding='utf-8'))
        return prefs if isinstance(prefs, dict) else {}
    except (OSError, ValueError):
        return {}


def ai_mode(uid: int) -> str:
    mode = ai_preferences(uid).get('mode', os.getenv('AI_MODE', 'auto'))
    return mode if mode in MODES else 'auto'


def save_ai_mode(uid: int, mode: str) -> None:
    f = user_dir(uid) / 'ai_preferences.json'
    tmp = f.with_suffix('.tmp')
    tmp.write_text(json.dumps({'mode': mode}), encoding='utf-8')
    tmp.replace(f)


def add_ai_to_report(report: dict, ai) -> None:
    # Nunca incluir segredos, conteúdo binário ou credenciais nas evidências.
    if ai.available:
        report['ai_analysis'] = ai.text
        report['ai_providers'] = ai.providers
    if ai.warnings:
        report['ai_warnings'] = ai.warnings


async def ai_analysis(prompt: str, evidence: dict|None, uid: int):
    return await asyncio.to_thread(explain_request, prompt, evidence, ai_mode(uid))


async def ai_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    status=provider_status()
    await update.effective_message.reply_text(
        f'🧠 DeepSeek/OpenRouter: {"✅ chave configurada" if status["deepseek"] else "❌ sem chave"}\n'
        f'Modelo DeepSeek: {status["deepseek_model"]}\n'
        f'Groq: {"✅ chave configurada" if status["groq"] else "❌ sem chave"}\n'
        f'Modelo Groq: {status["groq_model"]}\n'
        f'Modo atual: {ai_mode(update.effective_user.id)}\n'
        f'Assembly Worker: {"✅ instalado" if managed_available() else "❌ ausente"}\n'
        'Use /modelo deepseek, /modelo groq, /modelo auto ou /modelo dupla.\n'
        'Use /testaria para testar a conexão real. Chave configurada não garante acesso ao modelo.'
    )


async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    choice=' '.join(context.args).strip().lower()
    if choice not in MODES:
        await update.effective_message.reply_text(
            'Use /modelo deepseek, /modelo groq, /modelo auto ou /modelo dupla.\n'
            'auto: DeepSeek primeiro, Groq em fallback. dupla: duas análises independentes.'
        )
        return
    save_ai_mode(update.effective_user.id, choice)
    await update.effective_message.reply_text(f'Modo de IA atualizado: {choice}. Use /testaria para verificar.')


async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    text = ' '.join(context.args).strip()
    if not text:
        state_set(update.effective_user.id, {'mode': 'await_ai_request'})
        await update.effective_message.reply_text('Escreva sua pergunta técnica. A IA responderá com análise, sem editar arquivos automaticamente.')
        return
    await ai_respond(update, text)


async def ai_respond(update: Update, question: str):
    uid = update.effective_user.id
    answer = await ai_analysis(question, None, uid)
    if answer.available:
        output = f'🧠 IA ({", ".join(answer.providers)})\n\n{answer.text}'
    else:
        output = 'IA indisponível: configure OPENROUTER_API_KEY e/ou GROQ_API_KEY e confira as permissões dos modelos.'
    if answer.warnings:
        output += '\n\nAvisos: ' + '; '.join(answer.warnings)
    for i in range(0, len(output), 3700):
        await update.effective_message.reply_text(output[i:i+3700])
    state_set(uid, {})


async def test_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    await ai_respond(update, 'Teste de conectividade. Responda em uma frase curta: o que você consegue e o que não consegue fazer sem analisadores de binários?')


async def authorized(update:Update)->bool:
    uid=update.effective_user.id if update.effective_user else None
    if uid not in ALLOW:
        if update.effective_message:
            await update.effective_message.reply_text('Acesso privado. Seu Telegram ID não está autorizado.')
        return False
    return True


async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    await update.message.reply_text('SATANABE AI BUILDER v0.5\n\n/construir — receber Assembly e compilar módulo ESP\n/agente — DeepSeek/Groq chama ferramentas permitidas de análise\n/empacotar BUNDLE CAMINHO — gerar .3105 real a partir de arquivo\n/trocartexto ANTIGO | NOVO — substituir texto único em Assembly .NET\n/analisar — inspecionar arquivo/workspace\n/extrair — abrir .3105 e receber ZIP\n/atualizar — migrar alterações simples em JSON e .NET gerenciado\n/criar — planejar alterações\n/esp — configurações e DLL compilada\n/ia — DeepSeek ou Groq\n/modelo deepseek | groq | auto | dupla — escolher IA\n/statusia — status\n/testaria — testar a IA selecionada\n/senha — abrir pacote com senha\n/cancelar — limpar sessão\n\nESP compilada exige ligação ao jogo. IL2CPP/Unity nativo não admite edição automática genérica.',reply_markup=MENU)


async def analyze(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    state_set(update.effective_user.id, {'mode':'inspect'})
    await update.message.reply_text('Envie um arquivo (.3105, .bytes, cache_res, Assetindexer) ou um ZIP com o workspace exportado pelo 3105.')


async def extract_cmd(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    state_set(update.effective_user.id, {'mode':'extract'})
    await update.message.reply_text('Envie seu pacote .3105. Se não tiver senha, vou validar e devolver os arquivos em ZIP; se houver senha, vou solicitar a senha original.')


async def update_cmd(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    state_set(update.effective_user.id, {'mode':'await_package'})
    await update.message.reply_text('Envie o .3105 ou ZIP de workspace contendo a versão antiga modificada.\n\nDepois pedirei a versão nova e, para migração confiável, a antiga original. Para binários desconhecidos, só farei inspeção e relatório.')


async def create(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    prompt=' '.join(context.args).strip()
    if prompt:
        await send_plan(update,prompt)
    else:
        state_set(update.effective_user.id,{'mode':'await_request'})
        await update.message.reply_text('Escreva o que deseja criar, por exemplo: Crie um painel ESP com FOV vermelho, Line Tracer azul, Box verde, Skeleton amarelo e nome. Vou gerar uma especificação de interface; integração real precisa de um painel/renderer compatível.')


async def construir_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    prompt=' '.join(context.args).strip()
    if prompt:
        state_set(update.effective_user.id,{'mode':'await_build_assembly','request':prompt[:1800]})
        await update.message.reply_text('Envie um Assembly-CSharp (.dll/.bytes) ou .3105. Vou verificar o formato, gerar componente compatível e compilar o que for possível; ESP no jogo ainda exige adaptação de renderização e runtime.')
    else:
        state_set(update.effective_user.id,{'mode':'await_build_request'})
        await update.message.reply_text('Descreva o que deseja construir (ex.: Crie ESP com Box, Skeleton e nome). Depois pedirei o Assembly para análise.')


async def agente_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    prompt=' '.join(context.args).strip()
    if prompt:
        state_set(update.effective_user.id,{'mode':'await_agent_file','request':prompt[:1800]})
        await update.message.reply_text('Envie o arquivo a ser analisado. A Groq poderá solicitar inspeção e compilação pelo servidor (ferramentas permitidas).')
    else:
        state_set(update.effective_user.id,{'mode':'await_agent_request'})
        await update.message.reply_text('Descreva a tarefa para a IA; depois poderá anexar o arquivo.')


async def pack_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):return
    args=context.args
    if len(args)!=2:
        await update.message.reply_text('Formato: /empacotar com.seu.app Documents/nome.ext\nDepois envie o arquivo original ou modificado; o bot gera um .3105 para substituir esse caminho. Confira o Bundle ID e caminho antes de aplicar.')
        return
    bundle,relative=args
    # Destination is validated again in create3105.
    state_set(update.effective_user.id,{'mode':'await_pack_file','bundle':bundle,'relative':relative})
    await update.message.reply_text(f'Envie o arquivo que substituirá {relative} no aplicativo {bundle}. Vou gerar e verificar um .3105.')


async def replace_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    query=' '.join(context.args)
    if '|' not in query:
        await update.message.reply_text('Formato: /trocartexto TEXTO_ATUAL | TEXTO_NOVO\nDepois envie um Assembly .NET gerenciado. A substituição só ocorre se houver uma única correspondência.')
        return
    old,new=(x.strip() for x in query.split('|',1))
    if not old or len(old)>500 or len(new)>500:
        await update.message.reply_text('Texto inválido ou grande demais.')
        return
    state_set(update.effective_user.id,{'mode':'await_replace_assembly','before':old,'after':new})
    await update.message.reply_text('Envie o Assembly .NET gerenciado. Será gerada uma cópia; o original permanece intacto.')


async def _send_bytes(message,data:bytes,name:str,caption:str=''):
    if len(data)>49_000_000:
        await message.reply_text(f'{name}: acima do limite de envio do Telegram.');return
    await message.reply_document(document=InputFile(io.BytesIO(data),filename=name),caption=caption[:1000])


async def _bundle_from_entry(name:str):
    parts=PurePosixPath(name).parts
    if len(parts)>3 and parts[0]=='Application':
        return parts[1],'/'.join(parts[2:])
    return None


def esp_initial():
    return {key:{'enabled':False,'color':'#FFFFFF'} for key in ESP_FEATURES}


def esp_keyboard(controls):
    rows=[]
    for key,label in ESP_FEATURES.items():
        settings=controls[key]
        icon='✅' if settings['enabled'] else '⬜'
        line=[InlineKeyboardButton(f'{icon} {label}',callback_data=f'esp:t:{key}')]
        if key!='name':
            line.append(InlineKeyboardButton(f'🎨 {settings["color"]}',callback_data=f'esp:c:{key}'))
        rows.append(line)
    rows.append([InlineKeyboardButton('📄 Gerar receita',callback_data='esp:save')])
    return InlineKeyboardMarkup(rows)


async def esp_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    controls=esp_initial()
    state_set(update.effective_user.id,{'mode':'esp_menu','controls':controls})
    await update.message.reply_text('Personalize a interface ESP. Ative as opções e escolha as cores. Esta tela gera configuração visual, não código operacional de ESP.',reply_markup=esp_keyboard(controls))


async def esp_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    if not query: return
    if not await authorized(update):
        await query.answer('Não autorizado.',show_alert=True)
        return
    uid=update.effective_user.id
    state=read_state(uid)
    if state.get('mode')!='esp_menu':
        await query.answer('Menu expirado. Envie /esp.',show_alert=True)
        return
    parts=(query.data or '').split(':')
    controls=state.get('controls',{})
    if len(parts)<2 or parts[0]!='esp':
        await query.answer('Opção inválida.')
        return
    action=parts[1]
    if action=='save':
        spec={'schema_version':1,'kind':'esp_ui_specification',
              'controls':[{'feature':k,**v} for k,v in controls.items()],
              'requires_implementation':True,'require_validation':True,
              'note':'Somente configuração de interface; exige integração com um renderizador compatível.'}
        data=json.dumps(spec,ensure_ascii=False,indent=2).encode('utf-8')
        await query.answer('Receita preparada')
        await query.message.reply_document(document=InputFile(io.BytesIO(data),filename='satanabe-esp-interface.json'))
        await query.edit_message_text('Receita visual gerada. Tentando compilar o módulo de geometria ESP...')
        built=await asyncio.to_thread(build_overlay,controls)
        if built.get('success'):
            await _send_bytes(query.message,built['binary'],'SatanabeOverlay.dll', 'Biblioteca compilada. Recebe coordenadas; precisa de adaptador no jogo e não é Assembly-CSharp modificado.')
            await _send_bytes(query.message,built['source'].encode(),'SatanabeOverlay.cs')
        else:
            await query.message.reply_text('Não foi possível compilar: '+built.get('error','erro')[-900:])
        state_set(uid,{})
        return
    if action=='back':
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=esp_keyboard(controls))
        return
    if len(parts)<3 or parts[2] not in controls:
        await query.answer('Função inválida.')
        return
    key=parts[2]
    if action=='t':
        controls[key]['enabled']=not controls[key]['enabled']
        state_set(uid,{'mode':'esp_menu','controls':controls})
        await query.answer('Atualizado')
        await query.edit_message_reply_markup(reply_markup=esp_keyboard(controls))
        return
    if action=='c' and key!='name':
        buttons=[[InlineKeyboardButton(label,callback_data=f'esp:set:{key}:{code}')] for code,(color,label) in ESP_COLORS.items()]
        buttons.append([InlineKeyboardButton('⬅ Voltar',callback_data='esp:back')])
        await query.answer('Escolha uma cor')
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        return
    if action=='set' and len(parts)==4 and parts[3] in ESP_COLORS:
        controls[key]['color']=ESP_COLORS[parts[3]][0]
        state_set(uid,{'mode':'esp_menu','controls':controls})
        await query.answer('Cor atualizada')
        await query.edit_message_reply_markup(reply_markup=esp_keyboard(controls))
        return
    await query.answer('Opção inválida')


async def send_plan(update:Update,prompt:str):
    uid=update.effective_user.id
    spec=make_plan(prompt)
    if spec['kind']=='asset_analysis_request':
        state_set(uid,{'mode':'await_asset_for_design','request':prompt[:2000]})
        await update.effective_message.reply_text('Para este pedido, envie o arquivo Avatar/Assetindexer ou cache_res. Vou verificar o formato e montar um plano técnico. Sem conhecer a estrutura não criarei alterações de hitbox por suposição.')
        return
    ai=await ai_analysis(prompt, None, uid)
    add_ai_to_report(spec, ai)
    data=json.dumps(spec,ensure_ascii=False,indent=2).encode('utf-8')
    await update.effective_message.reply_document(document=InputFile(io.BytesIO(data),filename='satanabe-receita.json'),caption='Especificação gerada. Não é uma função operacional nem um patch .3105.')
    state_set(uid,{})


async def cancel(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):return
    state_set(update.effective_user.id,{})
    await update.message.reply_text('Sessão cancelada. Arquivos previamente enviados continuam armazenados no servidor até limpeza.')


async def select(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    uid=update.effective_user.id
    state=read_state(uid)
    if state.get('mode')!='await_selection':
        await update.message.reply_text('Nenhum pacote aguardando seleção.')
        return
    try: idx=int(context.args[0])-1
    except (IndexError,ValueError):
        await update.message.reply_text('Use /selecionar 1 (número exibido na lista).')
        return
    options=state.get('options',[])
    if idx<0 or idx>=len(options):
        await update.message.reply_text('Número não encontrado.')
        return
    state.update(mode='await_updated',entry_name=options[idx]['name'],category=options[idx]['category'])
    state_set(uid,state)
    await update.message.reply_text(f'Arquivo selecionado: {options[idx]["name"]}\n\nEnvie o arquivo ATUALIZADO correspondente.')


async def send_report(message, name:str, report:dict):
    data=json.dumps(report,ensure_ascii=False,indent=2).encode('utf8')
    await message.reply_document(document=InputFile(io.BytesIO(data),filename=name))


async def file_handler(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    msg=update.effective_message
    doc=msg.document
    uid=update.effective_user.id
    if doc.file_size and doc.file_size>MAX_TG_BYTES:
        await msg.reply_text('Arquivo acima do limite de download padrão do Telegram. Nesta base inicial, envie arquivo menor que 19 MB; upload grande via Safari será módulo posterior.')
        return
    state=read_state(uid)
    if not state:
        state={'mode':'inspect'}
    suffix=PurePosixPath(doc.file_name or 'upload.bin').suffix
    path=user_dir(uid)/(uuid4().hex+suffix)
    try:
        obj=await doc.get_file()
        await obj.download_to_drive(custom_path=str(path))
    except Exception:
        await msg.reply_text('Falha ao baixar arquivo. Verifique o limite de download da Bot API.')
        return
    if path.stat().st_size>MAX_TG_BYTES:
        path.unlink(missing_ok=True)
        await msg.reply_text('Arquivo excede limite permitido.')
        return
    details=inspect(path)
    if details.kind=='3105_protegido':
        state_set(uid,{'mode':'await_3105_password', 'previous_mode':state.get('mode','inspect'), 'package_path':str(path)})
        await msg.reply_text('🔒 Este .3105 possui senha. Envie /senha SUA_SENHA para abrir, ou /cancelar. '
                             'Não envie senha usada em outras contas: conversas com bots não têm criptografia ponta a ponta.')
        return
    await process_file(msg, uid, state, path, details, doc.file_name or path.name)


async def process_file(msg, uid, state, path, details, original_filename):
    mode=state.get('mode','inspect')
    if mode=='await_pack_file':
        if details.kind!='arquivo_solto':
            await msg.reply_text('Envie um arquivo individual, não um pacote ou ZIP.');return
        try:
            binary=create3105([(state['bundle'],state['relative'],path.read_bytes())],name='Satanabe AI Builder')
            await _send_bytes(msg,binary,'Satanabe_Gerado.3105','Pacote validado por reabertura criptográfica; aplicação no 3105/iPhone não foi testada.')
            await send_report(msg,'manifesto-build.json',{'bundle':state['bundle'],'relative_path':state['relative'],'source_sha256':details.sha256,'validacao':'roundtrip de criptografia e SHA256; não teste no jogo'})
        except (Patch3105Error,OSError,ValueError) as ex:
            await msg.reply_text('Falha no empacotamento: '+str(ex)[:400])
        state_set(uid,{})
        return
    if mode=='await_replace_assembly':
        output=user_dir(uid)/(uuid4().hex+path.suffix)
        try:
            report=await asyncio.to_thread(replace_string,path,output,state['before'],state['after'])
            await _send_bytes(msg,output.read_bytes(),original_filename,'Assembly modificado e reaberto com sucesso. Sem validação no jogo.')
            await send_report(msg,'relatorio-assembly.json',report)
        except (ManagedError,OSError,ValueError) as ex:
            await msg.reply_text('Não foi possível reescrever: '+str(ex)[:600])
        state_set(uid,{})
        return
    if mode=='await_build_assembly':
        evidence={'sha256':details.sha256,'kind':details.kind,'entries':[{'name':e.name,'signature':e.signature,'size':e.size} for e in details.entries[:12]]}
        assembly_path=path
        if details.kind in ('3105_decodificado','workspace_zip'):
            found=next((e for e in details.entries if e.category=='assembly'),None)
            if found:
                assembly_path=user_dir(uid)/(uuid4().hex+'.dll')
                assembly_path.write_bytes(read_entry(path,found.name))
                evidence['assembly_from_package']=found.name
        if details.kind=='arquivo_solto' or evidence.get('assembly_from_package'):
            try:
                evidence['managed']=await asyncio.to_thread(inspect_managed,assembly_path)
            except (ManagedError,ValueError) as exc:
                evidence['managed_error']=str(exc)[:350]
        if 'esp' in state['request'].lower():
            built=await asyncio.to_thread(build_overlay,{k:{'enabled':True,'color':'#FFFFFF'} for k in ESP_FEATURES})
            if built.get('success'):
                await _send_bytes(msg,built['binary'],'SatanabeOverlay.dll','Módulo geométrico compilado. NÃO é um Assembly-CSharp com ESP já integrado ao jogo.')
                await _send_bytes(msg,built['source'].encode(),'SatanabeOverlay.cs','Código-fonte do componente compilado.')
                evidence['build']={'compiled':True,'size':len(built['binary'])}
            else:
                evidence['build']={'compiled':False,'error':built.get('error','erro')[-1200:]}
        else:
            evidence['build']={'compiled':False,'reason':'Não existe compilador geral de modificações a partir de qualquer pedido; apenas ESP geométrica implementada.'}
        if provider_status()['deepseek'] or provider_status()['groq']:
            ai=await ai_analysis(state['request'],evidence,uid)
            add_ai_to_report(evidence,ai)
        await send_report(msg,'relatorio-build.json',evidence)
        await msg.reply_text('A integração real com câmera, personagens e renderização requer classes/interfaces compatíveis. O bot não instalou nem testou ESP dentro do jogo.')
        state_set(uid,{})
        return
    if mode=='await_agent_file':
        await msg.reply_text('Agente de IA analisando e escolhendo ferramentas permitidas...')
        try:
            report=await asyncio.to_thread(run_agent,state.get('request','Analisar arquivo'),path,esp_initial(),mode=ai_mode(uid))
            for filename,blob in report.pop('files',[]):
                await _send_bytes(msg,blob,filename,'Artefato compilado/gerado por ferramenta local.')
            response=report.get('response','') or 'Análise sem texto final.'
            for i in range(0,len(response),3500): await msg.reply_text(response[i:i+3500])
            await send_report(msg,'relatorio-agente.json',report)
        except RuntimeError as exc:
            await msg.reply_text('Agente IA indisponível: '+str(exc)[:550])
        state_set(uid,{})
        return
    if mode=='extract':
        if details.kind in ('3105_opaco', '3105_invalido', 'rejeitado'):
            await msg.reply_text(details.note)
            return
        if details.kind=='3105_decodificado':
            try:
                content=as_workspace_zip(path.read_bytes())
            except Patch3105Error as exc:
                await msg.reply_text(str(exc))
                return
        elif details.kind=='workspace_zip':
            content=path.read_bytes()
        else:
            await msg.reply_text('Envie um pacote .3105 compatível ou o ZIP do workspace correspondente.')
            return
        if len(content) > 49_000_000:
            await msg.reply_text('Extração acima do limite de envio do Telegram. Arquivo preservado no servidor; necessário módulo de download privado para recuperar.')
            return
        await msg.reply_document(document=InputFile(io.BytesIO(content),filename='Satanabe_3105_Extraido.zip'),caption='Arquivos do patch verificados e extraídos. Não significa que modificações binárias tenham sido atualizadas.')
        entries=[{'path':e.name,'type':e.category,'size':e.size,'sha256':e.sha256} for e in details.entries]
        await send_report(msg,'3105_manifesto.json',{'package':original_filename,'entries':entries,'note':details.note})
        state_set(uid,{})
        return
    if mode=='await_asset_for_design':
        spec=make_plan(state.get('request',''))
        spec['input_inspection']={
            'kind':details.kind,'sha256':details.sha256,'note':details.note,
            'entries':[{'path':e.name,'category':e.category,'signature':e.signature,'size':e.size} for e in details.entries[:25]]
        }
        ai=await ai_analysis(state.get('request',''),spec['input_inspection'],uid)
        add_ai_to_report(spec, ai)
        out=json.dumps(spec,ensure_ascii=False,indent=2).encode('utf-8')
        await msg.reply_document(document=InputFile(io.BytesIO(out),filename='satanabe-plano-de-asset.json'),caption='Plano e evidências do arquivo anexado. Nenhum binário foi alterado.')
        await msg.reply_text('Análise concluída. Para edição de hitbox/rig de um formato desconhecido ainda é necessário desenvolver e validar um adaptador específico.')
        state_set(uid,{})
        return
    if mode=='inspect':
        note=f'Inspeção: {details.file}\nTipo: {details.kind}\nSHA256: {details.sha256[:20]}…\n{details.note}\n'
        recognized=[e for e in details.entries if e.category!='outro']
        note+='\n'.join(f'• {e.category}: {e.name} ({e.signature})' for e in recognized[:20])
        await msg.reply_text(note[:3900])
        report=json.loads(details.json())
        # Só metadados e assinaturas limitados, sem enviar arquivos brutos à IA.
        evidence={'kind':details.kind,'note':details.note,
                  'entries':[{'category':e.category,'signature':e.signature,'size':e.size} for e in details.entries[:20]]}
        if provider_status()['deepseek'] or provider_status()['groq']:
            await msg.reply_text('Consultando a IA sobre os metadados do arquivo...')
            ai=await ai_analysis('Explique o formato provável, limitações e verificações adequadas. Não afirme que modificações foram extraídas.',evidence,uid)
            add_ai_to_report(report,ai)
        await send_report(msg,'relatorio-inspecao.json',report)
        return
    if mode=='await_package':
        if details.kind in ('3105_opaco','3105_invalido'):
            await msg.reply_text(details.note)
            return
        if details.kind=='rejeitado':
            await msg.reply_text(details.note)
            return
        options=[{'name':e.name,'category':e.category,'signature':e.signature} for e in details.entries if e.category!='outro']
        if not options:
            await msg.reply_text('Não identifiquei Assembly, cache_res ou Avatar. Envie o workspace contendo o caminho dos arquivos ou o arquivo com nome original.')
            return
        state.update(package=str(path),options=options)
        if len(options)==1:
            state.update(mode='await_updated',entry_name=options[0]['name'],category=options[0]['category'])
            state_set(uid,state)
            await msg.reply_text(f'Tipo identificado: {options[0]["category"]}\nArquivo: {options[0]["name"]}\n\nAgora envie a versão ATUALIZADA desse arquivo.')
        else:
            state['mode']='await_selection'
            state_set(uid,state)
            options_msg='Encontrei múltiplos arquivos:\n'+'\n'.join(f'{i+1}. [{e["category"]}] {e["name"]}' for i,e in enumerate(options[:20]))
            await msg.reply_text(options_msg[:3800]+'\n\nEscolha com /selecionar 1')
        return
    if mode=='await_updated':
        if details.kind in ('3105_opaco','3105_invalido'):
            await msg.reply_text('Envie o arquivo atualizado extraído, não outro pacote .3105 desconhecido.')
            return
        if details.kind=='workspace_zip':
            await msg.reply_text('Envie somente o arquivo atualizado desejado (Assembly, cache_res ou Assetindexer).')
            return
        current=details.entries[0].category
        if current!=state.get('category'):
            await msg.reply_text(f'O arquivo atualizado parece ser {current}, mas o arquivo selecionado era {state.get("category")}. Verifique o nome ou caminho.')
            return
        state.update(mode='await_old_original', updated=str(path), updated_name=original_filename)
        state_set(uid,state)
        await msg.reply_text('Versão nova recebida. Envie agora a versão ANTIGA ORIGINAL, sem modificações.\n\nCom três versões consigo isolar mudanças com mais segurança. Se for um binário desconhecido, entregarei um relatório, sem alterar bytes arbitrariamente.')
        return
    if mode=='await_old_original':
        if details.kind!='arquivo_solto':
            await msg.reply_text('Envie o arquivo antigo ORIGINAL, individualmente.')
            return
        if details.entries[0].category!=state['category']:
            await msg.reply_text('O tipo do original não corresponde ao selecionado.')
            return
        old_modified=read_entry(Path(state['package']),state['entry_name'])
        new_original=Path(state['updated']).read_bytes()
        old_original=path.read_bytes()
        report={'category':state['category'],'old_modified_entry':state['entry_name'],
                'old_modified_size':len(old_modified),'new_size':len(new_original),'baseline_size':len(old_original)}
        # Managed .NET CIL: three-way conservative transfer of unchanged IL instruction skeletons.
        if old_original[:2]==b'MZ' and old_modified[:2]==b'MZ' and new_original[:2]==b'MZ':
            try:
                tmpdir=user_dir(uid)
                base_file=tmpdir/(uuid4().hex+'.dll'); mod_file=tmpdir/(uuid4().hex+'.dll');out_file=tmpdir/(uuid4().hex+'.dll')
                base_file.write_bytes(old_original);mod_file.write_bytes(old_modified)
                diagnosis=await asyncio.to_thread(migrate_literals,base_file,mod_file,path,out_file)
                report.update(diagnosis)
                if diagnosis.get('applied',0)>0:
                    patched=out_file.read_bytes()
                    await _send_bytes(msg,patched,state.get('updated_name','Assembly-CSharp-patch.bytes'),'Literal CIL migrado; requires in-game compatibility validation.')
                    target=await _bundle_from_entry(state['entry_name'])
                    if target:
                        binary=create3105([(target[0],target[1],patched)],name='Satanabe Assembly Atualizado')
                        await _send_bytes(msg,binary,'Satanabe_Assembly_Atualizado.3105','Pacote gerado e reaberto, mas ainda não testado no jogo.')
                else:
                    await msg.reply_text('Nenhum literal seguro encontrado para transferir. Veja o relatório.')
                await send_report(msg,'relatorio-migracao.json',report)
                state_set(uid,{})
                return
            except (ManagedError,Patch3105Error,OSError,ValueError) as exc:
                report['managed_error']=str(exc)[:700]
                await msg.reply_text('Não consegui migrar Assembly gerenciado: '+str(exc)[:600]+'. Enviarei o diagnóstico.')
                await send_report(msg,'relatorio-migracao.json',report)
                state_set(uid,{})
                return
        try:
            migrated,diagnostics=migrate_json(old_original,old_modified,new_original)
            report.update(diagnostics)
            if diagnostics['conflicts']:
                report['status']='REVISÃO_NECESSÁRIA'
                await msg.reply_text('Encontrei conflitos. Nenhum resultado foi certificado ou exportado como patch válido.')
            else:
                report['status']='MIGRACAO_JSON_CONSERVADORA'
                output_name=PurePosixPath(state['updated_name']).name
                await msg.reply_document(document=InputFile(io.BytesIO(migrated),filename=output_name),caption='JSON migrado por comparação de três versões. Ainda requer testes no aplicativo.')
                parts=PurePosixPath(state['entry_name'].replace('\\','/')).parts
                if 'Application' in parts:
                    i=parts.index('Application')
                    bundle=parts[i+1] if i+1<len(parts) else ''
                    try:
                        packed=workspace_zip(state['entry_name'],migrated,bundle)
                        await msg.reply_document(document=InputFile(io.BytesIO(packed),filename='satanabe-workspace.zip'),caption='ZIP do workspace para importação no 3105. NÃO é um .3105 criptografado.')
                    except ValueError:
                        report['workspace']='Não gerado: Bundle ID/caminho ausente.'
        except (UnicodeError,ValueError,TypeError,json.JSONDecodeError):
            report['status']='BINARIO_SEM_ADAPTADOR'
            report['reason']='O arquivo não é JSON compatível. Uma migração de Assembly/Unity AssetBundle exige parser e receita estruturais específicos; não foi feita alteração automática.'
            await msg.reply_text('Arquivos analisados, mas não apliquei mudanças: este formato não tem um adaptador seguro implementado. Vou enviar o relatório de identificação.')
        if provider_status()['deepseek'] or provider_status()['groq']:
            evidence={'category':report['category'],'status':report['status'],
                      'sizes':{'old_modified':report['old_modified_size'],'old_original':report['baseline_size'],'new_original':report['new_size']},
                      'changes':report.get('changes'), 'conflicts':report.get('conflicts',[])[:10]}
            ai=await ai_analysis('Revise o diagnóstico desta migração e indique riscos e validações, sem inventar compatibilidade.',evidence,uid)
            add_ai_to_report(report, ai)
        await send_report(msg,'relatorio-migracao.json',report)
        state_set(uid,{})
        return
    await msg.reply_text('Use /analisar ou /atualizar para iniciar uma nova tarefa.')



async def unlock_patch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    uid=update.effective_user.id
    state=read_state(uid)
    if state.get('mode')!='await_3105_password':
        await update.effective_message.reply_text('Primeiro envie um pacote .3105 protegido usando /analisar ou /atualizar.')
        return
    password=' '.join(context.args)
    if not password:
        await update.effective_message.reply_text('Uso: /senha SENHA_DO_PACOTE (não use senhas de outras contas).')
        return
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    original=Path(state['package_path'])
    try:
        content=as_workspace_zip(original.read_bytes(),password)
        dest=user_dir(uid)/(uuid4().hex+'.zip')
        dest.write_bytes(content)
        details=inspect(dest)
    except (Patch3105Error, ValueError, OSError):
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text='Senha incorreta, arquivo incompatível ou pacote danificado. Tente /senha novamente ou /cancelar.')
        return
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text='🔓 Pacote aberto e conteúdo validado. Prosseguindo com os arquivos identificados.')
    await process_file(update.effective_message,uid,{'mode':state.get('previous_mode','inspect')},dest,details,original.name)


async def text_handler(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update):return
    txt=(update.message.text or '').strip()
    if txt.startswith('🔄'): return await update_cmd(update,context)
    if txt.startswith('🔍'): return await analyze(update,context)
    if txt.startswith('✨'): return await create(update,context)
    if txt.startswith('🤖'): return await ask_ai(update,context)
    if txt.startswith('🧠'): return await ai_status(update,context)
    if txt.startswith('❌'): return await cancel(update,context)
    state=read_state(update.effective_user.id)
    if state.get('mode')=='await_build_request':
        state_set(update.effective_user.id,{'mode':'await_build_assembly','request':txt[:1800]})
        return await update.message.reply_text('Agora envie o Assembly-CSharp (.dll/.bytes) ou o .3105 para análise e compilação.')
    if state.get('mode')=='await_agent_request':
        state_set(update.effective_user.id,{'mode':'await_agent_file','request':txt[:1800]})
        return await update.message.reply_text('Envie o arquivo para o agente Groq analisar e usar ferramentas.')
    if state.get('mode')=='await_request': return await send_plan(update,txt)
    if state.get('mode')=='await_ai_request': return await ai_respond(update,txt)
    # Conversa natural: pedidos que começam com criar viram receitas; demais textos viram perguntas à IA.
    if txt.lower().startswith(('crie ', 'criar ', 'faça ', 'faz ', 'adicione ', 'atualize ')):
        return await send_plan(update,txt)
    if provider_status()['deepseek'] or provider_status()['groq']:
        return await ai_respond(update,txt)
    await update.message.reply_text('Use /criar, /analisar, /atualizar ou configure as chaves de IA e envie sua pergunta.')


def main():
    token=os.getenv('TELEGRAM_BOT_TOKEN','')
    if not token: raise SystemExit('Configure TELEGRAM_BOT_TOKEN no servidor.')
    if not ALLOW: raise SystemExit('Configure ALLOWED_TELEGRAM_IDS; acesso negado por padrão.')
    app=Application.builder().token(token).concurrent_updates(False).build()
    app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('ajuda',start))
    app.add_handler(CommandHandler('analisar',analyze))
    app.add_handler(CommandHandler('extrair',extract_cmd))
    app.add_handler(CommandHandler('atualizar',update_cmd))
    app.add_handler(CommandHandler('criar',create))
    app.add_handler(CommandHandler('construir',construir_cmd))
    app.add_handler(CommandHandler('agente',agente_cmd))
    app.add_handler(CommandHandler('empacotar',pack_cmd))
    app.add_handler(CommandHandler('trocartexto',replace_cmd))
    app.add_handler(CommandHandler('selecionar',select))
    app.add_handler(CommandHandler('esp',esp_cmd))
    app.add_handler(CommandHandler('ia',ask_ai))
    app.add_handler(CommandHandler('modelo',set_model))
    app.add_handler(CommandHandler('statusia',ai_status))
    app.add_handler(CommandHandler('testaria',test_ai))
    app.add_handler(CommandHandler('senha',unlock_patch))
    app.add_handler(CallbackQueryHandler(esp_callback,pattern=r'^esp:'))
    app.add_handler(CommandHandler('cancelar',cancel))
    app.add_handler(MessageHandler(filters.Document.ALL,file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__':main()
