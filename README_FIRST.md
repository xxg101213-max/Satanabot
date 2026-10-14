# SATANABE AI BUILDER — v0.2.1 — LEIA PRIMEIRO

**Integração da IA concluída no código; implantação e teste nas contas reais ainda exigem suas chaves.** Este projeto é um bot Telegram Python que usa Gemini 3.8 Flash + Groq GPT-OSS 120B de modo opcional. As chamadas HTTP são feitas no **servidor**, nunca no iPhone. **Não existem chaves de terceiros embutidas no ZIP.**

## O que está implementado e verificado

- Telegram privado (requer token e Telegram ID); comandos e botões de menus.
- **Gemini**: integração REST `generateContent`, modelo padrão `gemini-3.8-flash`.
- **Groq**: integração REST Chat Completions, modelo padrão `openai/gpt-oss-120b`.
- Modos `/modelo auto`, `/modelo gemini`, `/modelo groq`, `/modelo dupla` (configuração individual por Telegram ID).
- **Auto**: Gemini em primeiro lugar; se faltar a chave, houver erro ou o Gemini não responder, tenta Groq.
- **Dupla**: pede parecer independente dos dois modelos e mostra ambos. **Não é garantia de exatidão.**
- `/ia <pergunta>`; `/statusia` para ver configuração sem revelar chaves; `/testaria` para fazer uma chamada real.
- IA integrada a `/criar`, análise de formatos em `/analisar`, diagnósticos de migração JSON e inspeção dos assets enviados como entrada de criação.
- Erros de credenciais, limites de quota, timeout e modelo indisponível viram mensagens em português. O bot continua operando com funções locais se as APIs não estiverem disponíveis.
- Inspeção por caminho e assinatura de arquivos (Assembly, `cache_res`, Avatar), ZIP/workspace com limites de tamanho; classificação de `.3105` opaco; migração conservadora de JSON com 3 versões; especificações ESP/FOV/Box/Line Tracer/Skeleton/Nome; workspace ZIP para 3105.
- Testes unitários para APIs simuladas sem usar créditos, fallback, revisão dupla e núcleo de classificação.

**Ainda não disponível:** decodificação de `.3105` criptografado, edição autônoma de Assembly/IL2CPP/`cache_res`/`Assetindexer`, ESP funcional, hitbox, bala mágica e exportação do pacote `.3105` criptografado. As IAs geram **análises e planos**; não inventam modificações binárias. A geração de ZIP de workspace não equivale a um `.3105` final.

## Instruções para iPhone (Telegram + Safari)

1. No Telegram abra https://t.me/BotFather, use `/newbot`, defina nome e username e **guarde o token**.
2. Descubra seu Telegram ID numérico. Use esse valor em `ALLOWED_TELEGRAM_IDS` no servidor.
3. No Safari abra https://aistudio.google.com/apikey e crie sua chave `GEMINI_API_KEY`, na modalidade gratuita quando disponível. Em https://console.groq.com/keys crie `GROQ_API_KEY` para o plano gratuito. **Não envie as chaves neste chat ou no Telegram.**
4. Envie este projeto descompactado para um repositório GitHub **privado**. Não publique arquivo `.env` com chaves.
5. Conecte-o à hospedagem com suporte a Docker e worker persistente (por exemplo, Railway). No painel **Variables / Secrets**, defina:

   ```text
   TELEGRAM_BOT_TOKEN=<token do BotFather>
   ALLOWED_TELEGRAM_IDS=<seu ID numérico>
   GEMINI_API_KEY=<chave do Google AI Studio>
   GROQ_API_KEY=<chave Groq>
   GEMINI_MODEL=gemini-3.8-flash
   GROQ_MODEL=openai/gpt-oss-120b
   AI_MODE=auto
   DATA_DIR=/data
   ```

6. Configure um volume persistente montado em `/data` para preservar estados e uploads entre reinicializações. Use **somente 1 réplica** do worker polling. O `Dockerfile` inicia o bot automaticamente.
7. Abra o bot no Telegram: `/start`, `/statusia`, `/testaria`. Faça `/modelo dupla` para análise independente dos dois modelos, `/ia Como identificar o formato do Assembly?` para perguntar, `/analisar` para enviar arquivos e `/atualizar` para comparar versões.

*Notas de custo*: a API Google/Groq tem cotas gratuitas sujeitas a disponibilidade, limite por minuto/dia e regras das plataformas; não são uso ilimitado. **Hospedagem e armazenamento podem cobrar**. Modo `dupla` consome quota de ambos os provedores. `statusia` só vê se uma variável está preenchida, não confirma acesso: é para isso que existe `/testaria`.

*Privacidade*: nomes, tamanhos, tipos, hashes e outros **metadados** dos arquivos podem ser enviados ao Google/Groq durante a análise. Os arquivos binários não são transmitidos a essas APIs. Os textos dos seus pedidos também são enviados. A disponibilidade da modalidade gratuita e as regras de uso de dados são definidas pelo provedor.

## Comandos

| Comando | Ação |
|---|---|
| `/start` | Menu principal |
| `/statusia` | Exibir provedores configurados e modelos |
| `/testaria` | Chamada real de teste da IA |
| `/modelo auto` | Gemini → Groq como reserva (padrão) |
| `/modelo dupla` | Consultar ambos de forma independente |
| `/modelo gemini` | Preferir Gemini, com fallback Groq |
| `/modelo groq` | Preferir Groq, com fallback Gemini |
| `/ia <texto>` | Consultar IA sem anexar binários |
| `/criar <texto>` | Gerar especificação técnica com parecer da IA |
| `/esp` | Configurar interface ESP visual por botões |
| `/analisar` | Inspecionar arquivo/ZIP e gerar relatório |
| `/atualizar` | Iniciar comparação de três versões (migração real só de JSON) |
| `/selecionar 1` | Escolher arquivo de um workspace com múltiplos candidatos |
| `/cancelar` | Limpar fluxo atual; mantém preferência de modelo |

## Fluxo de atualização

`/atualizar` → envie ZIP de workspace com versão antiga *modificada* → selecione arquivo → envie a versão *nova original* → envie a versão *antiga original*. O motor só migra alterações JSON compatíveis; se houver conflito, gera relatório. Binários não são alterados automaticamente. Um arquivo `.3105` opaco não pode ser presumido como ZIP: exporte o workspace pelo app antes.

## Testes e operação

Localmente na raiz do repositório:

```bash
python -m unittest discover -s tests -v
python -m satanabe_builder.bot
```

Se o bot não responde: revise `ALLOWED_TELEGRAM_IDS`, token do BotFather, a disponibilidade do container e os logs. Se a IA não responde: `/statusia` + `/testaria`; erros 401, 403, 404 e 429 indicam respectivamente credencial, acesso, modelo, limite/cota. Não coloque segredos em relatórios ou capturas de tela.

A implementação usa somente a biblioteca padrão do Python para os dois clientes REST de IA; a dependência de runtime é `python-telegram-bot==22.5`. Não é necessário pagar por SDK nem instalar bibliotecas de IA extras.

Documentação: https://ai.google.dev/gemini-api/docs/generate-content/text-generation | https://ai.google.dev/gemini-api/docs/pricing | https://console.groq.com/docs/api-reference | https://console.groq.com/docs/rate-limits | https://github.com/YangJiiii/3105 .

## Conversa natural

Depois de `/start`, o bot também entende texto simples. Pedidos iniciados por `crie`, `criar`, `faça`, `adicione` ou `atualize` seguem o planejador de receitas. Outras mensagens viram perguntas à IA, quando alguma chave estiver configurada. Isso não permite gravação automática em binários.

## GitHub Actions

O arquivo `.github/workflows/tests.yml` faz instalação de dependências, compilação e testes automaticamente quando houver push em `main` ou pull request. Nenhuma chave de IA é exigida nesse workflow: os testes da API usam respostas simuladas.


## Compatibilidade Gemini 3.8 (v0.2.1)

Removido o parâmetro `temperature` da requisição REST do Gemini 3.8 Flash, conforme orientação de migração do Google para modelos Gemini 3.6+. O bot permanece usando `generateContent` como documentado para a API legada.
