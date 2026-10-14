# Satanabe AI Builder v0.5 — DeepSeek gratuito + Groq

## Novidade

- DeepSeek V4 Flash 0731 gratuito **via OpenRouter**, modelo `deepseek/deepseek-v4-flash-0731:free`.
- Comandos: `/modelo deepseek`, `/modelo groq`, `/modelo auto` (DeepSeek e fallback Groq), `/modelo dupla` (pareceres independentes).
- `/statusia` mostra o provedor e o modelo sem revelar segredos.
- `/testaria` chama realmente o provedor selecionado.
- `/agente` seleciona o provedor preferido para chamar apenas ferramentas de inspeção e compilação previamente autorizadas. Modos auto/dupla preferem DeepSeek; fallback Groq. Modo dupla não duplica builds do agente.
- Nenhuma integração Gemini. `/agente` não aplica patches desconhecidos nem injeta ESP em jogos de terceiros.

## 1 — Criar chave sem cartão para modelo gratuito

1. Abra https://openrouter.ai/settings/keys e entre na sua conta.
2. Clique em **Create Key**, crie uma chave e copie-a. **Não envie chaves pelo Telegram, ChatGPT ou GitHub**.
3. Verifique o modelo gratuito disponível em https://openrouter.ai/deepseek/deepseek-v4-flash-0731:free

## 2 — Publicar pelo iPhone

1. Envie **Satanabe_AI_Builder_v0.5_DeepSeek_OpenRouter.zip** para a raiz do repositório privado `xxg101213-max/Satanabot` no GitHub.
2. Abra **Code → Codespaces**, inicie um codespace na `main` e execute o terminal:

```sh
unzip -o Satanabe_AI_Builder_v0.5_DeepSeek_OpenRouter.zip
cp -a satanabe-ai-builder-v0.5/. .
rm -rf satanabe-ai-builder-v0.5 Satanabe_AI_Builder_v0.5_DeepSeek_OpenRouter.zip
python -m compileall -q satanabe_builder
python -m unittest discover -s tests -v
git add -A
git commit -m "Satanabe Builder v0.5 DeepSeek via OpenRouter"
git push
```

3. Na Railway, entre no serviço Satanabot → Variables e **mantenha suas variáveis existentes**. Adicione apenas:

```
OPENROUTER_API_KEY=SUA_CHAVE_PRIVADA_NOVA
OPENROUTER_MODEL=deepseek/deepseek-v4-flash-0731:free
AI_MODE=auto
```

4. Aplique o deploy e confirme se a inicialização permanece `Active`.

## 3 — Testar Telegram

- `/start`
- `/statusia`
- `/modelo deepseek`
- `/testaria`
- `/ia Explique a diferença entre assembly gerenciado e IL2CPP`
- `/modelo dupla` e `/testaria` (usa duas chamadas e consome cotas dos provedores).

## Observações

O modelo `:free` tem limites de taxa/solicitações e pode estar temporariamente indisponível. O bot não usa modelos OpenRouter pagos se `OPENROUTER_MODEL` não terminar em `:free` e começar com `deepseek/`.

As chaves não estão embutidas no ZIP. O Gemini não é mais necessário. Se Groq também estiver configurado, entra como reserva.

Os recursos binários do bot continuam com as restrições já descritas na v0.4: análise e migração conservadora para .NET gerenciado, leitor/gravação .3105 compatíveis e compilação isolada de módulo de geometria, sem injeção automática de ESP funcional ou modificação de hitbox/Avatar.
