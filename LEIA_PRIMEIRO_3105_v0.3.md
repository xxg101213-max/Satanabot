# Satanabe AI Builder v0.3 — Leitor .3105

Atualização incremental sobre o repositório GitHub `xxg101213-max/Satanabot`.

## O que foi adicionado

- Reconhece pacotes com cabeçalho `3105PATCH\0`, schemas 1, 2 e 3 usados no codec público do projeto 3105.
- Lê envelope binário plist, verifica integridade SHA-256, descriptografa AES-256-GCM.
- Se pacote **não tem senha**, usa a chave pública **incluída no próprio envelope**, como no projeto original.
- Se tem senha, solicita `/senha SENHA_DO_PACOTE`, deriva chave PBKDF2-HMAC-SHA256 e verifica autenticidade AES-GCM. Não adivinha senhas. O comando tenta apagar a mensagem contendo senha, mas bots do Telegram não oferecem criptografia ponta a ponta — evite reutilizar senhas pessoais.
- `/analisar`: identifica os arquivos no pacote e produz um relatório JSON.
- `/extrair`: recebe `.3105` compatível e devolve ZIP com arquivos e um manifesto de SHA-256.
- `/atualizar`: aceita pacotes compatíveis para iniciar a seleção de Assembly, cache_res ou avatar. **A migração automática de binários continua não implementada.**

## Instalação no GitHub pelo iPhone

**A API de gravação no GitHub negou acesso (HTTP 403); esta alteração não foi enviada ao seu repositório.**

O ZIP contém apenas os quatro arquivos que devem atualizar seu projeto GitHub: `requirements.txt`, `satanabe_builder/bot.py`, `satanabe_builder/core.py` e `satanabe_builder/patch3105.py`.

1. Baixe `Satanabe_AI_Builder_Patch3105_v0.3.zip`.
2. Faça upload desse ZIP na **raiz** do seu repositório GitHub (Add file → Upload files → Commit changes).
3. Abra GitHub → Code → Codespaces → seu Codespace (ou crie um novo).
4. No terminal do Codespaces, execute:

```sh
unzip -o Satanabe_AI_Builder_Patch3105_v0.3.zip
rm Satanabe_AI_Builder_Patch3105_v0.3.zip
git add requirements.txt satanabe_builder/bot.py satanabe_builder/core.py satanabe_builder/patch3105.py
# Como o arquivo ZIP também foi commitado no GitHub, remova-o do histórico de trabalho:
git add -u
git commit -m "Integrar leitor de pacotes 3105"
git push
```

5. No Railway, o serviço conectado ao GitHub deverá gerar novo deploy. Mantenha suas variáveis já configuradas. Nenhuma variável adicional é necessária.
6. No Telegram, teste `/start`, `/extrair`, envie um `.3105` seu e, se necessário, use `/senha SENHA_DO_PACOTE`.

## Limitações reais

- Suporte inicial aos schemas **v1 a v3** do código público `PatchPackageCodec.swift`. Pacotes de versões diferentes podem ter outro formato, mesmo com extensão `.3105`, e precisarão de um adaptador adicional.
- O teste realizado foi com pacotes **sintéticos**, sem senha e com senha, gerados conforme o formato publicado. **Não foi testado com o `.3105` real do usuário**.
- Apenas leitura, extração e classificação. A edição de Assembly/IL2CPP, cache_res ou Assetindexer continua exigindo implementações próprias.
- Este projeto usa Python com `cryptography`, não compila nem executa a aplicação iOS 3105 em Railway.
- Arquivos e senhas só devem ser usados se você tiver autorização; o bot não remove proteções sem a senha correta.
- Fonte e licença do projeto de referência: https://github.com/YangJiiii/3105 (GPLv3). Este código é uma implementação de compatibilidade em Python, baseada na descrição pública do formato, sem copiar o aplicativo iOS.
