# SATANABE AI BUILDER v0.6 — instalar pelo iPhone

## Problema corrigido

O bot guardava um arquivo chamado `Assembly-CSharp-patch.bytes` com nome UUID (`af16....bytes`) e tentava classificar o tipo usando o UUID. Isso fazia `categoria=outro`, interrompendo o fluxo.

Também havia risco de perder o estado ao usar `/testaria` ou `/analisar` no meio da atualização. Ambos agora preservam o processo (a análise avisa que já existe tarefa ativa). Corrigido um `await` aplicado indevidamente a uma função síncrona.

## O que o modo `/atualizar` pede

1. `.3105` que contém o Assembly antigo COM modificações.
2. Assembly-CSharp NOVO sem modificações, enviado como arquivo no Telegram.
3. Assembly-CSharp ANTIGO ORIGINAL, da mesma versão do patch, sem modificações.

A comparação em três vias distingue modificações do painel de diferenças da atualização do jogo. A transferência de literais só se aplica a .NET gerenciado, e alterações binárias pequenas são aplicadas apenas quando os padrões do original antigo aparecem de forma única e exatamente igual no novo. Não garante atualizar ESP, aim smooth ou outros sistemas IL2CPP.

Se você só possui os arquivos (1) e (2), o programa não tem informação suficiente para identificar automaticamente todas as alterações. Em vez de prometer sucesso, explica qual original ou receita comprovada está faltando.

## Instalação

1. Salve `Satanabe_AI_Builder_v0.6_Correcao_Atualizar.zip` no Arquivos do iPhone.
2. Faça upload desse ZIP para a raiz do GitHub `xxg101213-max/Satanabot`.
3. Abra GitHub → Code → Codespaces → Terminal e execute APENAS os comandos, sem copiar os caracteres do prompt `(main) $`:

```bash
unzip -o Satanabe_AI_Builder_v0.6_Correcao_Atualizar.zip
cp -a satanabe-ai-builder-v0.6/. .
rm -rf satanabe-ai-builder-v0.6 Satanabe_AI_Builder_v0.6_Correcao_Atualizar.zip
git add -A
git commit -m "Fix assembly update flow v0.6"
git push origin main
```

4. Railway → Satanabot → Deployments: confira a nova implantação. As chaves Groq e OpenRouter são mantidas em `Variables`, não no GitHub.
5. Railway: adicione volume montado em `/data` (se não houver), pois `DATA_DIR=/data` sem volume pode perder os estados após reinícios.
6. Telegram: envie `/start`, depois `/atualizar`; mande os três arquivos em sequência e use `/etapa` para conferir a etapa.

## Verificações executadas

31 testes Python locais aprovados. Não foi testado um Assembly real de Free Fire nem uma modificação de ESP funcional no iPhone. O build .NET da Railway não foi executado neste ambiente.
