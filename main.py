
import os
import uuid
from typing import Dict

import requests # Adicionado import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from bot import TRT2Bot

app = FastAPI()

# Variáveis de ambiente
TRIBUNAL_URL_BASE = os.getenv("TRIBUNAL_URL_BASE", "https://pje.trt2.jus.br/pje-consulta-api/api")
API_KEY_2CAPTCHA = os.getenv("API_KEY_2CAPTCHA", "YOUR_2CAPTCHA_API_KEY")

# Inicializa o bot
trt2_bot = TRT2Bot(tribunal_url_base=TRIBUNAL_URL_BASE, api_key_2captcha=API_KEY_2CAPTCHA)

# Armazenamento em memória para desafios de captcha em andamento
# Em um ambiente de produção, isso deveria ser um armazenamento persistente (ex: Redis)
ongoing_challenges: Dict[str, Dict] = {}

class ProcessoRequest(BaseModel):
    numero_processo: str

class CaptchaResolveRequest(BaseModel):
    challenge_id: str
    resposta: str

@app.get("/", tags=["Health Check"])
async def read_root():
    return {"status": "online"}

@app.post("/consultar_processo", tags=["Processo"])
async def consultar_processo(request: ProcessoRequest):
    try:
        result = trt2_bot.obter_dados_processo(request.numero_processo)

        if result["status"] == "captcha_required":
            challenge_id = result["challenge_id"]
            # Armazena os dados necessários para resolver o captcha posteriormente
            ongoing_challenges[challenge_id] = {
                "numero_processo": request.numero_processo,
                "imagem_captcha_base64": result["imagem_captcha_base64"],
                # O token_desafio será obtido novamente pelo bot quando o captcha for resolvido
                # ou pode ser armazenado aqui se o bot o retornar junto com captcha_required
            }
            return {"status": "captcha_required", "challenge_id": challenge_id, "imagem_captcha_base64": result["imagem_captcha_base64"]}
        elif result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Erro desconhecido"))

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Erro de comunicação com o serviço externo: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")

@app.post("/resolver_captcha", tags=["Processo"])
async def resolver_captcha(request: CaptchaResolveRequest):
    challenge_data = ongoing_challenges.get(request.challenge_id)
    if not challenge_data:
        raise HTTPException(status_code=404, detail="Challenge ID inválido ou expirado.")

    numero_processo = challenge_data["numero_processo"]
    # O token_desafio precisa ser obtido novamente pelo bot ou armazenado no challenge_data
    # Para simplificar, vamos assumir que o bot pode re-obter o token_desafio
    # ou que ele foi armazenado no challenge_data quando o captcha_required foi retornado.
    # No bot.py, a lógica foi ajustada para re-obter o token_desafio se não for passado.

    try:
        # Chama o bot para tentar resolver o captcha com a resposta do usuário
        # Passamos a resposta do usuário e o token_desafio (se disponível no challenge_data)
        # O bot.py foi ajustado para lidar com isso.
        result = trt2_bot.obter_dados_processo(
            numero_processo=numero_processo,
            captcha_resposta=request.resposta,
            token_desafio=None # O bot.py vai re-obter o token_desafio se necessário
        )

        if result["status"] == "success":
            del ongoing_challenges[request.challenge_id] # Remove o desafio após sucesso
            return result
        elif result["status"] == "captcha_failed":
            # Se o captcha falhou, podemos retornar captcha_required novamente com um novo challenge_id
            # ou simplesmente informar que a resposta estava incorreta.
            # Para este caso, vamos retornar captcha_failed e o challenge_id original para nova tentativa.
            return {"status": "captcha_failed", "message": result.get("message", "Resposta do captcha incorreta."), "challenge_id": request.challenge_id, "imagem_captcha_base64": challenge_data["imagem_captcha_base64"]}
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Erro desconhecido ao resolver captcha."))

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Erro de comunicação com o serviço externo: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")

