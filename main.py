from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional
import base64
import uuid
import os

# Importar a lógica do robô (agora bot.py)
from bot import TRT2Bot

app = FastAPI(title="TRT2/TRT15 Scraper API - Easypanel")

# CONFIGURAÇÃO DE CORS - Essencial para o Lovable conseguir acessar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Em produção, você pode restringir ao domínio do seu Lovable
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instância do bot (a chave 2captcha pode ser passada por variável de ambiente no Easypanel)
# A URL base do tribunal pode ser configurada aqui ou via variável de ambiente para TRT15
API_KEY_2CAPTCHA = os.getenv("API_KEY_2CAPTCHA", "ec722dea728475be0087f0666ca83772")
TRIBUNAL_URL_BASE = os.getenv("TRIBUNAL_URL_BASE", "https://pje.trt2.jus.br/pje-consulta-api/api/processos")

bot = TRT2Bot(api_key_2captcha=API_KEY_2CAPTCHA, tribunal_url_base=TRIBUNAL_URL_BASE)

# Dicionário para armazenar desafios de captcha pendentes para intervenção humana
ongoing_challenges: Dict[str, Dict] = {}

class ProcessoRequest(BaseModel):
    numero_processo: str

class CaptchaResponse(BaseModel):
    challenge_id: str
    resposta: str

@app.get("/")
async def root():
    return {"status": "online", "message": "TRT2/TRT15 Scraper API rodando no Easypanel"}

@app.post("/consultar_processo")
async def consultar_processo(request: ProcessoRequest):
    numero_processo = request.numero_processo
    print(f"[*] Recebida consulta para: {numero_processo}")
    
    try:
        # O método obter_dados_processo agora lida com a lógica de captcha híbrida
        resultado = bot.obter_dados_processo(numero_processo)

        if resultado.get("status") == "captcha_required":
            challenge_id = str(uuid.uuid4())
            ongoing_challenges[challenge_id] = {
                "numero_processo": numero_processo,
                "processo_id": resultado["processo_id"],
                "token_desafio": resultado["token_desafio"]
            }
            return {
                "status": "captcha_required",
                "challenge_id": challenge_id,
                "imagem_captcha_base64": resultado["imagem_captcha_base64"]
            }
        elif resultado.get("status") == "captcha_failed":
            raise HTTPException(status_code=400, detail=resultado["message"])
        elif resultado.get("status") == "success":
            return JSONResponse(content=resultado["data"])
        else:
            raise HTTPException(status_code=500, detail="Erro inesperado na consulta do processo.")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro de conexão com o TRT2: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")

@app.post("/resolver_captcha")
async def resolver_captcha(response: CaptchaResponse):
    challenge_data = ongoing_challenges.pop(response.challenge_id, None)
    if not challenge_data:
        raise HTTPException(status_code=404, detail="Desafio de captcha expirado ou não encontrado.")

    try:
        # Tenta obter os dados novamente com a resposta humana
        resultado_final = bot.obter_dados_processo(
            numero_processo=challenge_data["numero_processo"],
            captcha_resposta=response.resposta,
            token_desafio=challenge_data["token_desafio"],
            processo_id=challenge_data["processo_id"]
        )
        
        if resultado_final.get("status") == "success":
            return JSONResponse(content=resultado_final["data"])
        elif resultado_final.get("status") == "captcha_failed":
            raise HTTPException(status_code=400, detail=resultado_final["message"])
        else:
            raise HTTPException(status_code=500, detail="Erro inesperado ao resolver captcha.")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro de conexão com o TRT2: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")
