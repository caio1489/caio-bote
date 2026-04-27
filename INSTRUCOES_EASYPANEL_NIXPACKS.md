# Guia de Instalação: TRT2 Scraper no Easypanel (Nixpacks) + JurisSync (Lovable)

Este guia detalha como implantar o robô de scraping do TRT2 no Easypanel usando o método Nixpacks e como integrá-lo ao seu frontend JurisSync (Lovable).

## 1. Preparação dos Arquivos no GitHub

Para usar o Nixpacks, precisamos de uma estrutura de arquivos mais limpa no seu repositório do GitHub.

1.  Acesse seu repositório no GitHub (`caio1489/bot-trt2-scraper`).
2.  **Renomeie** o arquivo `trt2_automacao_final_com_chave.py` para **`bot.py`**.
3.  **Renomeie** o arquivo `requisitos.txt` (se ainda estiver com esse nome) para **`requirements.txt`**.
4.  **APAGUE** o arquivo **`Dockerfile`** (o Nixpacks gera o dele automaticamente).
5.  **APAGUE** o arquivo **`INSTRUCOES_EASYPANEL.md`** (este novo guia o substitui).
6.  **APAGUE** o arquivo **`LovableComponent.tsx`** (o novo `TRT2ScraperComponent.tsx` o substitui).
7.  **Faça upload** dos novos arquivos que você recebeu:
    *   `bot.py` (o robô atualizado)
    *   `main.py` (a API FastAPI atualizada)
    *   `requirements.txt` (as dependências)
    *   `TRT2ScraperComponent.tsx` (o componente React para o JurisSync)
    *   `INSTRUCOES_EASYPANEL_NIXPACKS.md` (este guia)
8.  Faça um **Commit** das mudanças no GitHub.

## 2. Configuração no Easypanel

1.  No seu painel do **Easypanel**, entre no serviço que você criou para o robô do TRT2.
2.  Vá para a aba **"Fonte"** (ou **"Source"**).
3.  **Conecte ao GitHub** (se ainda não estiver) e selecione seu repositório (`caio1489/bot-trt2-scraper`).
4.  No campo **"Ramo"**, digite **`principal`**.
5.  No campo **"Caminho de Build"**, deixe **`/`**.
6.  No campo **"Método de Build"**, selecione **`Nixpacks`**.
7.  Clique em **"Salvar"**.

## 3. Configurações de Ambiente e Comandos (Nixpacks)

Agora, vamos configurar o Nixpacks para que ele instale tudo corretamente:

1.  Vá para a aba **"Ambiente"** (ou **"Environment"**).
2.  Adicione as seguintes variáveis:
    *   **`PORT`**: `8000`
    *   **`API_KEY_2CAPTCHA`**: `ec722dea728475be0087f0666ca83772` (sua chave do 2Captcha)
    *   **`TRIBUNAL_URL_BASE`**: `https://pje.trt2.jus.br/pje-consulta-api/api/processos` (para TRT2; para TRT15, você criaria outro serviço e mudaria esta URL)
    *   **`NIXPACKS_PYTHON_VERSION`**: `3.11` (força a versão do Python)
    *   **`NIXPACKS_PKGS`**: `libgl1 libglib2.0-0` (instala as dependências de sistema para o OCR)
3.  Clique em **"Salvar"**.

4.  Vá para a aba **"Geral"** (ou **"General"**).
5.  No campo **"Comando de Início"** (ou **"Start Command"**), cole:
    `python -m uvicorn main:app --host 0.0.0.0 --port 8000`
6.  Clique em **"Salvar"**.

## 4. Deploy Final

1.  No topo da página do seu serviço, clique no botão **"Implantar"** (ou **"Deploy"**).
2.  Acompanhe os **"Logs"**. Você verá o Nixpacks construindo o ambiente e instalando as dependências.
3.  Quando o deploy for concluído com sucesso, o status do serviço mudará para **"Running"** ou **"Online"**.
4.  Vá na aba **"Domínios"** (ou **"Domains"**) e copie a URL do seu serviço (ex: `https://trt2-bot.seuservidor.com`).

## 5. Integração no JurisSync (Lovable)

1.  No seu projeto **JurisSync** no Lovable, crie um novo arquivo em `src/components/` (ou onde você organiza seus componentes) chamado **`TRT2ScraperComponent.tsx`**.
2.  Cole o conteúdo do arquivo `TRT2ScraperComponent.tsx` que você recebeu neste novo arquivo.
3.  **MUITO IMPORTANTE**: No topo do `TRT2ScraperComponent.tsx`, substitua a `API_BASE_URL` pela URL que você copiou do Easypanel:
    ```typescript
    const API_BASE_URL = "https://seu-dominio-do-easypanel.com"; // <-- COLOQUE AQUI A URL DO SEU SERVIÇO NO EASYPANEL
    ```
4.  Agora você pode usar o `<TRT2ScraperComponent />` em qualquer lugar do seu JurisSync para adicionar a funcionalidade de consulta do TRT2.

---

Com este guia, seu robô estará online no Easypanel e pronto para ser integrado ao JurisSync. Se tiver qualquer problema ou dúvida em algum passo, me avise!
