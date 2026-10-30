# 🛡️ Política e Relatório de Segurança da Informação (SI)
**Projeto:** Campus Vision (Sistema de Sinalização Digital & TV Corporativa)  
**Data da Avaliação:** Outubro / 2026  
**Classificação:** Confidencial / Uso Interno  
**Versão:** 1.0.0  

---

## 1. Sumário Executivo

Este documento apresenta a **Avaliação de Risco de Segurança da Informação (Risk Assessment)** e as **Diretrizes de Hardening** para a arquitetura, infraestrutura e código-fonte da plataforma **Campus Vision**.

O objetivo é identificar vulnerabilidades potenciais segundo as melhores práticas de mercado (OWASP Top 10, CIS Benchmarks, NIST e ISO/IEC 27001), classificar os riscos por impacto e probabilidade, e estabelecer um plano de ação claro para mitigação.

---

## 2. Matriz de Avaliação de Riscos (OWASP Top 10)

| ID | Categoria OWASP | Vulnerabilidade / Risco Identificado | Severidade | Status Atual |
| :--- | :--- | :--- | :---: | :---: |
| **SEC-01** | A01:2021 - Broken Access Control | Falta de `@login_required` e checagem de permissão em rotas administrativas (`/upload/`, `/settings/`, `/usermanager/`, etc.). | 🔴 **CRÍTICA** | Mapeado |
| **SEC-02** | A02:2021 - Cryptographic Failures | Credenciais do banco MySQL TiDB e `SECRET_KEY` em texto claro no `settings.py`. | 🔴 **CRÍTICA** | Mapeado |
| **SEC-03** | A05:2021 - Security Misconfiguration | `DEBUG = True` fixo no código de produção e `ALLOWED_HOSTS = ['*']`. | 🟠 **ALTA** | Mapeado |
| **SEC-04** | A02:2021 - Cryptographic Failures | Comunicação HTTP em texto puro (ausência de TLS/HTTPS obrigatório). | 🟠 **ALTA** | Mapeado |
| **SEC-05** | A04:2021 - Insecure Design / DoS | Upload de arquivos validado apenas por extensão, sem limite rígido de payload ou checagem de MIME/Magic Bytes. | 🟡 **MÉDIA** | Mapeado |
| **SEC-06** | A07:2021 - Identification & Auth Failures | Política de senhas fraca (`min_length: 4`) e ausência de Rate Limiting na tela de login. | 🟡 **MÉDIA** | Mapeado |
| **SEC-07** | A03:2021 - Injection / SSRF | Inclusão de URLs Embed sem whitelist de domínios confiáveis ou sandbox no iframe. | 🟡 **MÉDIA** | Mapeado |
| **SEC-08** | A09:2021 - Logging & Monitoring Failures | Falta de trilha de auditoria estruturada para ações críticas de usuários e moderação. | 🟢 **BAIXA** | Mapeado |

---

## 3. Detalhamento Técnico das Vulnerabilidades

### 🔴 SEC-01: Controle de Acesso Quebrado (Broken Access Control)
- **Localização:** `campusvision_django/app/views.py`
- **Descrição:** Várias views de gerenciamento (`upload_file`, `edit`, `moderate`, `moderate_post`, `settings_view`, `configuration_equipment`, `usermanager`, `bus_manager`, `alerts`, `messages_view`) não aplicam o decorador `@login_required` nem verificam se o usuário possui `is_admin=True`.
- **Impacto:** Um invasor que acesse diretamente as rotas administrativas pode cadastrar mídias, aprovar/reprovar conteúdos nas TVs, alterar mensagens de emergência, modificar configurações ou excluir equipamentos sem estar autenticado.
- **Recomendação:**
  1. Aplicar decoradores `@login_required` em todas as rotas administrativas e de criação.
  2. Criar um decorador `@admin_required` para rotas sensíveis (`/settings/`, `/usermanager/`, `/mod/`, `/configuration_equipment/`).
  3. Manter públicas exclusivamente as rotas de exibição das TVs (`/feeds/<title>/`, `/feeds-vertical/<title>/`) e seus endpoints de leitura (`/api/feed/<feed_name>/`).

---

### 🔴 SEC-02: Exposição de Credenciais e Segredos em Texto Claro
- **Localização:** `campusvision_django/campusvision_django/settings.py`
- **Descrição:** As credenciais de conexão do banco de dados TiDB Cloud (`USER`, `PASSWORD`, `HOST`, `PORT`), a chave de API de clima (`WEATHER_KEY`) e o fallback de `SECRET_KEY` estão presentes em texto puro no arquivo versionado no Git.
- **Impacto:** Qualquer pessoa com acesso de leitura ao repositório obtém acesso total e irrestrito ao banco de dados em nuvem e à chave de assinatura de sessões e CSRF do Django.
- **Recomendação:**
  1. Rotacionar imediatamente a senha do banco de dados no TiDB Cloud.
  2. Carregar todas as credenciais exclusivamente através de Variáveis de Ambiente (`.env` ou `os.environ`), utilizando bibliotecas como `python-dotenv` ou `dj-database-url`.
  3. Adicionar o arquivo `.env` ao `.gitignore`.

---

### 🟠 SEC-03: Configurações de Segurança Inadequadas (Security Misconfiguration)
- **Localização:** `campusvision_django/campusvision_django/settings.py`
- **Descrição:**
  - `DEBUG = True` expõe o depurador interativo do Django e variáveis de ambiente em caso de falha de execução.
  - `ALLOWED_HOSTS = ['*']` abre brecha para ataques de envenenamento de cache e injeção de Host Header.
  - Falta de cabeçalhos de segurança HTTP (HSTS, Content-Type-Nosniff, XSS-Filter, CSP).
- **Recomendação:**
  1. Configurar `DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1')`.
  2. Definir explicitamente `ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '35.243.187.172,localhost').split(',')`.
  3. Ativar flags de cookies e cabeçalhos de segurança:
     ```python
     SESSION_COOKIE_HTTPONLY = True
     SECURE_CONTENT_TYPE_NOSNIFF = True
     X_FRAME_OPTIONS = 'SAMEORIGIN'
     ```

---

### 🟠 SEC-04: Falta de Criptografia em Trânsito (HTTPS/TLS)
- **Localização:** Nginx / Servidor de Aplicação (`35.243.187.172`)
- **Descrição:** A aplicação está sendo servida via protocolo HTTP desprotegido (porta 80).
- **Impacto:** Sessões administrativas, senhas digitadas no login e dados em trânsito podem ser interceptados por ataques do tipo Man-in-the-Middle (MitM) na rede local ou internet.
- **Recomendação:**
  1. Configurar um domínio DNS (ex: `tv.campus.edu.br` ou similar).
  2. Gerar e instalar um certificado SSL/TLS gratuito com **Let's Encrypt (Certbot)** no Nginx.
  3. Ativar o redirecionamento automático de HTTP para HTTPS:
     ```python
     SECURE_SSL_REDIRECT = True
     SECURE_HSTS_SECONDS = 31536000
     SESSION_COOKIE_SECURE = True
     CSRF_COOKIE_SECURE = True
     ```

---

### 🟡 SEC-05: Upload de Arquivos sem Validação Estrita de Conteúdo e Payload
- **Localização:** `campusvision_django/app/views.py` (`upload_file`)
- **Descrição:** Apenas a extensão do arquivo é verificada (`allowed_file`). Um atacante poderia enviar um arquivo `.jpg` ou `.png` contendo código HTML/JavaScript malicioso (Polyglot) ou arquivos excessivamente grandes (GigaBytes) para esgotar o armazenamento do servidor.
- **Recomendação:**
  1. Limitar o tamanho máximo de upload no Django (`DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024` - 50MB) e no Nginx (`client_max_body_size 50M;`).
  2. Validar o MIME-type real do arquivo utilizando `python-magic` ou `PIL.Image.verify()` para imagens.
  3. Desabilitar execução de scripts na pasta de uploads no Nginx (`location /static/uploads/ { ... }`).

---

### 🟡 SEC-06: Política de Senhas e Ausência de Rate Limiting
- **Localização:** `campusvision_django/campusvision_django/settings.py` e `app/views.py`
- **Descrição:** `AUTH_PASSWORD_VALIDATORS` aceita senhas de apenas 4 caracteres e não há proteção contra ataques de força bruta no endpoint de login.
- **Recomendação:**
  1. Habilitar os validadores padrão do Django (tamanho mínimo de 8 caracteres, complexidade, verificação contra senhas comuns).
  2. Implementar `django-ratelimit` ou configurar `limit_req` no Nginx para o endpoint `/login/` (ex: máximo de 5 tentativas por minuto por IP).

---

### 🟡 SEC-07: Inclusão de Embeds e Risco de Iframe Injection
- **Localização:** `campusvision_django/app/templates/app/feed.html`
- **Descrição:** URLs cadastradas para painéis são incorporadas em `<iframe>` sem restrições de sandbox.
- **Recomendação:**
  1. Validar se a URL pertence a protocolos seguros (`https://`).
  2. Opcionalmente, implementar uma whitelist de domínios permitidos para painéis corporativos (ex: `app.powerbi.com`, `grafana.com`, `lookerstudio.google.com`).
  3. Aplicar atributos de sandbox quando apropriado (`sandbox="allow-scripts allow-same-origin allow-popups"`).

---

## 4. Plano de Ação & Roadmap de Correção (Hardening)

### Fase 1: Imediato (Correções Críticas - 24 a 48h)
1. Proteger todas as views com autenticação obrigatória (`@login_required`).
2. Migrar credenciais do banco e chaves para variáveis de ambiente (`.env`).
3. Desativar `DEBUG = True` em produção.

### Fase 2: Curto Prazo (Infraestrutura & Rede - 1 semana)
1. Instalar Certificado SSL (HTTPS) no servidor Nginx via Certbot.
2. Configurar rate limiting no Nginx para rotas sensíveis.
3. Ajustar `ALLOWED_HOSTS` e regras de CORS/CSRF.

### Fase 3: Médio Prazo (Monitoramento & Auditoria - 2 semanas)
1. Adicionar logs estruturados de auditoria para ações de moderação e upload.
2. Configurar backups automáticos do banco de dados e arquivos de mídia.

---

## 5. Diretrizes para a Equipe de TI e Operadores

- **Contas de Acesso:** Cada operador deve possuir seu próprio usuário individual. O compartilhamento de senhas é estritamente proibido.
- **Mídias e Conteúdos:** Mídias enviadas para veiculação pública devem ser validadas previamente no fluxo de moderação.
- **Atualizações:** Manter o sistema operacional Linux (Ubuntu/Debian), pacotes Python e Nginx atualizados com os patches de segurança mais recentes (`sudo apt update && sudo apt upgrade`).
