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
    status = provider_status()
    mode = ai_mode(update.effective_user.id)
    await update.effective_message.reply_text(
        '🧠 SATANABE AI — STATUS\n'
        f'Gemini: {"✅ configurado" if status["gemini"] else "❌ sem chave"} ({status["gemini_model"]})\n'
        f'Groq: {"✅ configurado" if status["groq"] else "❌ sem chave"} ({status["groq_model"]})\n'
        f'Modo atual: {mode}\n\n'
        'Use /modelo auto | gemini | groq | dupla\n'
        'Use /ia seu pedido para conversar.\n'
        'Use /testaria para fazer uma chamada real.\n'
        '✅ configurado não significa que a chave já foi testada.'
    )


async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    choice = ' '.join(context.args).strip().lower()
    if choice not in MODES:
        await update.effective_message.reply_text(
            'Escolha: /modelo auto, /modelo gemini, /modelo groq ou /modelo dupla.\n'
            'auto: Gemini primeiro e Groq como reserva; dupla: parecer independente dos dois modelos.'
        )
        return
    save_ai_mode(update.effective_user.id, choice)
    await update.effective_message.reply_text(f'Modo de IA atualizado: {choice}. Use /statusia para ver quais chaves estão disponíveis.')


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
        output = 'IA indisponível: configure GEMINI_API_KEY e/ou GROQ_API_KEY nos segredos da hospedagem.'
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
    await update.message.reply_text('SATANABE AI BUILDER\n\n/analisar — inspecionar arquivo ou workspace\n/atualizar — comparar e migrar versões\n/criar — gerar especificação de uma função/interface\n/esp — escolher interface por botões\n/ia — consultar Gemini/Groq\n/modelo — escolher auto, gemini, groq ou dupla\n/statusia — status de configuração\n/testaria — testar conexão externa\n/cancelar — limpar sessão\n\nLimites: pacotes .3105 criptografados não podem ser identificados sem exportação do workspace; binários não são reescritos automaticamente.',reply_markup=MENU)


async def analyze(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await authorized(update): return
    state_set(update.effective_user.id, {'mode':'inspect'})
    await update.message.reply_text('Envie um arquivo (.3105, .bytes, cache_res, Assetindexer) ou um ZIP com o workspace exportado pelo 3105.')


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
        await query.edit_message_text('Receita de interface gerada. Use /esp para configurar outra.')
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
    mode=state.get('mode','inspect')
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
        if provider_status()['gemini'] or provider_status()['groq']:
            await msg.reply_text('Consultando a IA sobre os metadados do arquivo...')
            ai=await ai_analysis('Explique o formato provável, limitações e verificações adequadas. Não afirme que modificações foram extraídas.',evidence,uid)
            add_ai_to_report(report,ai)
        await send_report(msg,'relatorio-inspecao.json',report)
        return
    if mode=='await_package':
        if details.kind=='3105_opaco':
            await msg.reply_text('Não consegui enxergar o conteúdo interno: este .3105 não está em ZIP legível. Abra no aplicativo 3105, acesse o workspace correspondente, compacte a pasta e envie o ZIP para que eu identifique o arquivo sem inventar seu conteúdo.')
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
        if details.kind=='3105_opaco':
            await msg.reply_text('Envie o arquivo atualizado extraído, não outro pacote .3105 opaco.')
            return
        if details.kind=='workspace_zip':
            await msg.reply_text('Envie somente o arquivo atualizado desejado (Assembly, cache_res ou Assetindexer).')
            return
        current=details.entries[0].category
        if current!=state.get('category'):
            await msg.reply_text(f'O arquivo atualizado parece ser {current}, mas o arquivo selecionado era {state.get("category")}. Verifique o nome ou caminho.')
            return
        state.update(mode='await_old_original', updated=str(path), updated_name=doc.file_name or path.name)
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
        if provider_status()['gemini'] or provider_status()['groq']:
            evidence={'category':report['category'],'status':report['status'],
                      'sizes':{'old_modified':report['old_modified_size'],'old_original':report['baseline_size'],'new_original':report['new_size']},
                      'changes':report.get('changes'), 'conflicts':report.get('conflicts',[])[:10]}
            ai=await ai_analysis('Revise o diagnóstico desta migração e indique riscos e validações, sem inventar compatibilidade.',evidence,uid)
            add_ai_to_report(report, ai)
        await send_report(msg,'relatorio-migracao.json',report)
        state_set(uid,{})
        return
    await msg.reply_text('Use /analisar ou /atualizar para iniciar uma nova tarefa.')


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
    if state.get('mode')=='await_request': return await send_plan(update,txt)
    if state.get('mode')=='await_ai_request': return await ai_respond(update,txt)
    # Conversa natural: pedidos que começam com criar viram receitas; demais textos viram perguntas à IA.
    if txt.lower().startswith(('crie ', 'criar ', 'faça ', 'faz ', 'adicione ', 'atualize ')):
        return await send_plan(update,txt)
    if provider_status()['gemini'] or provider_status()['groq']:
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
    app.add_handler(CommandHandler('atualizar',update_cmd))
    app.add_handler(CommandHandler('criar',create))
    app.add_handler(CommandHandler('selecionar',select))
    app.add_handler(CommandHandler('esp',esp_cmd))
    app.add_handler(CommandHandler('ia',ask_ai))
    app.add_handler(CommandHandler('modelo',set_model))
    app.add_handler(CommandHandler('statusia',ai_status))
    app.add_handler(CommandHandler('testaria',test_ai))
    app.add_handler(CallbackQueryHandler(esp_callback,pattern=r'^esp:'))
    app.add_handler(CommandHandler('cancelar',cancel))
    app.add_handler(MessageHandler(filters.Document.ALL,file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__':main()
