# AGENTS.md — No Radar do Jarbis

## Objetivo

Bot Python de afiliados da Amazon que lê ofertas de canais e grupos do Telegram, filtra e reformula mensagens, converte URLs para a tag `noradardojarb-20` e publica no canal `@noradardojarbis`.

## Arquitetura atual

- `Telethon`/MTProto lê `SOURCE_CHANNEL_IDS` com uma conta de usuário e revisa as 10 mensagens mais recentes ao iniciar ou reconectar.
- `python-telegram-bot` publica via Bot API.
- `src/filters.py` filtra ofertas; `src/converters.py` extrai e formata dados e URLs.
- `src/state.py` mantém deduplicação no SQLite `config/state.db`, em WAL.
- O ponto de entrada é `python -m src.bot`; na VM, `radar-jarbis.service` o executa via systemd.
- Mídia é processada em memória e não deve ser persistida no banco.

## Arquivos importantes

- `src/bot.py`: orquestra captura, histórico, processamento e publicação.
- `src/settings.py`: carrega `.env` da raiz ou, como fallback, `config/.env`.
- `src/filters.py`: categorias, exclusões e desconto mínimo.
- `src/converters.py`: título, preço, cupom, ASIN, URL de afiliado e HTML final.
- `src/state.py`: schema, consultas e atualizações SQLite.
- `tests/`: testes automatizados de conversão, filtros e deduplicação.
- `config/.env.example`: referência de configuração, sem credenciais reais.
- `config/context/`: regras funcionais e de copywriting.
- `radar-jarbis.service.example`: modelo do serviço systemd.

## Comandos confirmados

Execute a partir da raiz do repositório:

```bash
# Instalar dependências
.venv/bin/pip install -r requirements.txt

# Executar localmente
.venv/bin/python -m src.bot

# Executar testes
.venv/bin/python -m unittest discover -s tests -v

# Validar sintaxe
.venv/bin/python -m compileall -q src tests

# Ver logs do serviço na VM
sudo journalctl -u radar-jarbis.service -f -n 50

# Reiniciar o serviço na VM
sudo systemctl restart radar-jarbis.service
```

## Restrições

- Nunca registrar, exibir ou incluir em commits tokens, senhas, hashes, chaves, `.env` ou sessões Telethon.
- Nunca modificar `.env` automaticamente.
- Nunca remover o SQLite antes da validação completa do Supabase e de um rollback testado.
- Não alterar captura, reformulação, tag de afiliado, conversão de URL ou publicação sem solicitação explícita.
- Preservar compatibilidade com Ubuntu 24.04 e VM e2-micro de 1 GB; evitar dependências pesadas e pools grandes.
- Não armazenar imagens ou vídeos no SQLite, PostgreSQL ou Supabase.
- Fazer mudanças pequenas, reversíveis e cobertas por testes.
- Durante a migração, manter SQLite como fallback e tratar divergências da escrita dupla explicitamente.

## Convenções Python do projeto

- Python com quatro espaços, type hints e docstrings nas funções principais.
- Código assíncrono com `asyncio`; não bloquear o event loop com rede ou banco síncrono demorado.
- Imports internos relativos (`from . import ...`) e execução por módulo (`python -m src.bot`).
- Testes com `unittest`, `IsolatedAsyncioTestCase`, mocks e SQLite temporário.
- Logging estruturado; nunca interpolar credenciais ou conteúdo secreto.
- Manter persistência isolada em `state.py` ou em repositórios equivalentes.

## Critério de conclusão

Uma mudança só está concluída quando o código e a sintaxe foram validados, os testes pertinentes foram executados, a documentação foi atualizada, o rollback foi descrito e nenhum segredo foi incluído no diff ou em commits.
