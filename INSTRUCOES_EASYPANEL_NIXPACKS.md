# Configuração Easypanel / Nixpacks

Para que o ddddocr e o curl_cffi funcionem corretamente, adicione estas configurações no seu Easypanel:

## 1. Variáveis de Ambiente (Environment)
Vá na aba **Environment** e adicione:
- `NIXPACKS_APT_PKGS` = `libgl1 libglib2.0-0`
- `NIXPACKS_PYTHON_VERSION` = `3.11`
- `PYTHONUNBUFFERED` = `1`
- `PORT` = `8000`
- `TRIBUNAL_URL_BASE` = `https://pje.trt2.jus.br/pje-consulta-api/api/processos`
- `API_KEY_2CAPTCHA` = `SUA_CHAVE_AQUI`

## 2. Deploy
- Clique em **Save**.
- Clique em **Deploy** (ou Redeploy).
- Se houver erro de instalação, tente fazer o deploy com a opção **"Clear Cache"** marcada.
