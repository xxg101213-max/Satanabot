# Satanabe AI Builder — Guia completo só com iPhone (v0.2.1)

## Antes de começar

Você precisa de um iPhone, Telegram, Safari, aplicativo Arquivos, conta GitHub, Google AI Studio, Groq e Railway. Faça todos os cadastros com suas próprias contas. Não envie tokens ou chaves a outras pessoas nem os publique no GitHub. O bot ainda não edita binários de jogo automaticamente: ele oferece inspeção, relatórios, configuração visual e migração segura de JSON.

## 1. Telegram

1. No Telegram acesse https://t.me/BotFather, envie `/newbot`, escolha nome `Satanabe AI Builder` e um username único terminado em `bot`.
2. Guarde o token enviado pelo BotFather. Ele será a variável `TELEGRAM_BOT_TOKEN`.
3. Acesse https://t.me/userinfobot, toque em Start e anote seu ID numérico. Ele será `ALLOWED_TELEGRAM_IDS`.

## 2. Chaves gratuitas (sujeitas a limites)

1. No Safari, entre em https://aistudio.google.com/apikey, crie uma API key e guarde: `GEMINI_API_KEY`.
2. Entre em https://console.groq.com/keys, crie uma API key e guarde: `GROQ_API_KEY`.
3. Não edite `.env.example` para colocar as chaves; use apenas os segredos da Railway.

## 3. GitHub: colocar o código pelo iPhone

1. Faça download do ZIP `Satanabe_AI_Builder_v0.2.1_iPhone.zip` e salve no app Arquivos do iPhone.
2. No Safari entre em https://github.com/new, crie repositório **privado** chamado `satanabe-ai-builder`, selecione **Add a README file** e crie o repositório.
3. No repositório toque em **Add file > Upload files**. Selecione o ZIP a partir de **Escolher Arquivos**; faça commit em `main`. Isto ainda não extrai o ZIP.
4. Toque em **Code > Codespaces > Create codespace on main**. No iPhone, se necessário, use `aA > Solicitar Site para Computador` no Safari.
5. No editor Codespaces abra **Terminal > New Terminal**, cole estes comandos (cada linha ou o bloco inteiro):

```bash
unzip -o Satanabe_AI_Builder_v0.2.1_iPhone.zip
cp -a satanabe-ai-builder/. .
rm -rf satanabe-ai-builder Satanabe_AI_Builder_v0.2.1_iPhone.zip
git add -A
git commit -m "Install Satanabe AI Builder v0.2.1"
git push
```

6. Volte ao GitHub e confirme que `Dockerfile`, `requirements.txt` e a pasta `satanabe_builder/` aparecem **na raiz**, fora de qualquer ZIP. Termine a sessão Codespaces quando concluir, para poupar sua quota gratuita.

## 4. Railway: implantar o worker

1. Entre em https://railway.com, faça login com GitHub e crie um projeto (`New Project`).
2. Escolha `Deploy from GitHub Repo` ou crie um serviço e depois `Settings > Source > Connect Repo`. Selecione seu repositório privado.
3. O Railway deve detectar `Dockerfile`. Não é necessário domínio público, endpoint HTTP, servidor web nem variáveis PORT para este bot (usa Telegram long polling).
4. Em `Variables` configure:

```text
TELEGRAM_BOT_TOKEN=<SEU TOKEN BOTFATHER>
ALLOWED_TELEGRAM_IDS=<SEU TELEGRAM ID NUMERICO>
GEMINI_API_KEY=<SUA CHAVE GEMINI>
GROQ_API_KEY=<SUA CHAVE GROQ>
GEMINI_MODEL=gemini-3.8-flash
GROQ_MODEL=openai/gpt-oss-120b
AI_MODE=auto
DATA_DIR=/data
```

5. Para persistência, adicione um **Volume** vinculado ao serviço e defina o **Mount path** `/data` (se seu plano oferecer volume). Se não houver volume disponível, o bot pode iniciar, mas configurações e uploads locais poderão desaparecer após reinícios/deploys.
6. Defina `Replicas = 1` se houver essa opção; não execute o bot ao mesmo tempo no Codespaces ou em outra Railway. O bot usa polling, e duas instâncias podem conflitar.
7. Faça `Deploy`/`Redeploy`. Em `Logs` procure se o processo inicia sem erro e permanece em execução. O Dockerfile contém o comando de inicialização.

## 5. Teste no Telegram

1. Abra o bot criado pelo BotFather e envie `/start`.
2. Envie `/statusia` e confirme ambos os provedores configurados.
3. Envie `/testaria` e confira uma resposta real. Caso falhe, abra `Logs` na Railway e verifique as variáveis.
4. Envie `/modelo dupla` para consultar duas IAs, e `/ia explique diferenças entre assemblies gerenciados e IL2CPP`.
5. Envie `/esp` para gerar especificação visual; `/analisar` para enviar um arquivo ou ZIP de workspace; `/atualizar` para iniciar comparação de versões.

## 6. Limitações e custos

- Gemini 3.8 Flash tem cota gratuita, sujeita a limites e disponibilidade. Groq possui modalidade gratuita com limites. No modo dupla, os dois serviços são consultados.
- Railway informa teste de 30 dias ou US$ 5 em créditos, e depois plano Free com US$ 1 de crédito mensal; não é garantia de execução contínua sem custos. O plano Hobby possui custo. Confira https://docs.railway.com/pricing/free-trial.
- Workspace ZIP do aplicativo 3105 não equivale a pacote `.3105` criptografado. Para este bot, `.3105` opaco exige extração por ferramenta compatível, e não se pode prometer modificação direta de Assembly, cache_res, Avatar, ESP, hitbox ou bala mágica.
- Nenhuma chamada real a Gemini ou Groq foi testada sem suas chaves privadas. Testes locais simulados verificam a lógica do código.

## 7. Soluções rápidas para erros

- `/start` não responde: token ou bot não implantado; verifique `Logs`, `TELEGRAM_BOT_TOKEN`, `ALLOWED_TELEGRAM_IDS`; bot e ID corretos.
- `Acesso privado`: corrija ID numérico em `ALLOWED_TELEGRAM_IDS`.
- Gemini retorna 401/403/404/429: chave inválida, acesso insuficiente, modelo indisponível para conta, ou cota atingida. Confira `/testaria` e `Logs`; o modo `auto` pode tentar Groq.
- `Conflict terminated by other getUpdates`: existe outra instância lendo o mesmo token. Mantenha uma única réplica; se houve webhook anterior, ele precisará ser removido antes de usar polling.
- Deployment falha com `No start command`: certifique que o `Dockerfile` está na raiz e foi detectado no serviço.
- O bot perdeu uploads: configure volume montado em `/data`.
