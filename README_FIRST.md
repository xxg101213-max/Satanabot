# SATANABE AI BUILDER v0.6 — Correção de Atualizar

# SATANABE AI BUILDER v0.5 — DeepSeek + Groq

Versão completa para Telegram/iPhone e Railway, a partir da v0.4. Mantém leitor e gerador 3105, Assembly Worker .NET, gerador de componente geométrico e ferramentas de inspeção conservadoras.

**Novo:** DeepSeek `deepseek/deepseek-v4-flash-0731:free` via OpenRouter, com Groq como fallback. Suporte a `/modelo deepseek`, `/modelo groq`, `/modelo auto`, `/modelo dupla`, `/statusia`, `/testaria`, `/agente`. Nenhuma chave Gemini necessária. Somente o modelo `:free` é aceito em OpenRouter para evitar cobrança acidental.

## Instalação

Leia **INSTALACAO_V05_IPHONE.md**. No Railway, adicione `OPENROUTER_API_KEY` e, opcionalmente, `OPENROUTER_MODEL`. Conserve os tokens de Telegram e Groq existentes. `AI_MODE=auto` usa DeepSeek primeiro.

## Limites

Adicionar IA **não** faz o bot transformar automaticamente um Assembly-CSharp de jogo IL2CPP em um arquivo com ESP funcionando. A compilação do módulo ESP gera somente uma biblioteca isolada; para renderizar num jogo seria necessário um adaptador e dados apropriados. Hitbox, cache_res e Avatar seguem sem reescrita binária genérica. O leitor `.3105` requer senha original quando o pacote é protegido.

## Licença, testes, segurança

Veja `LICENSE`, `THIRD_PARTY_NOTICES.md`, `tests/` e `.github/workflows/tests.yml`. Não coloque chaves no repositório.


## Correção v0.6
- Identifica o arquivo recebido pelo nome original do Telegram em vez do UUID local (evita categoria `outro`).
- Comando `/etapa` indica o próximo arquivo. `/analisar` não interrompe sessões de atualização por engano.
- `/testaria` e perguntas IA não apagam mais o fluxo de atualização em andamento.
- Corrigido uso de `await` em função síncrona do pacote 3105.
- Nova migração conservadora para arquivos binários com modificações PEQUENAS e de mesmo tamanho, exigindo: original antigo + patch antigo + novo original; o destino só é alterado quando todas as âncoras são únicas e idênticas.
- NÃO transfere ESP/aim smooth/painel arbitrários em IL2CPP quando as estruturas mudaram; não garante execução no jogo.
- Se âncoras falharem, o bot explica e não produz uma modificação falsa.
- Comando recomendado: `/atualizar`, depois 3 envios consecutivos de arquivo. Nunca use `/analisar` entre eles.

O bot ainda precisa ser publicado no GitHub/Railway. Não coloque chaves em arquivos versionados.
