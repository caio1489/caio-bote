import os
import requests
from typing import Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from bot import TRT2Bot

app = FastAPI(title="JurisSync TRT2 Scraper API")

# Configurações via Variáveis de Ambiente
TRIBUNAL_URL_BASE = os.getenv("TRIBUNAL_URL_BASE", "https://pje.trt2.jus.br/pje-consulta-api/api/processos" )
API_KEY_2CAPTCHA = os.getenv("API_KEY_2CAPTCHA", "")

# Inicializa o bot (Singleton)
bot = TRT2Bot(tribunal_url_base=TRIBUNAL_URL_BASE, api_key_2captcha=API_KEY_2CAPTCHA)

# Armazenamento em memória para desafios pendentes
ongoing_challenges: Dict[str, Dict] = {}

class ConsultaRequest(BaseModel):
    numero_processo: str

class ResolverRequest(BaseModel):
    challenge_id: str
    resposta: str

@app.get("/")
async def health_check():
    return {"status": "online", "tribunal": "TRT2"}

@app.post("/consultar_processo")
async def consultar_processo(req: ConsultaRequest):
    try:
        resultado = bot.obter_dados_processo(req.numero_processo)
        
        if resultado["status"] == "captcha_required":
            challenge_id = resultado["challenge_id"]
            ongoing_challenges[challenge_id] = {
                "numero_processo": req.numero_processo,
                "token_desafio": resultado["token_desafio"],
                "imagem_captcha_base64": resultado["imagem_captcha_base64"]
            }
            return resultado
            
        if resultado["status"] == "success":
            return resultado
            
        return resultado
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resolver_captcha")
async def resolver_captcha(req: ResolverRequest):
    challenge = ongoing_challenges.get(req.challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Desafio expirado ou inexistente.")
    
    try:
        resultado = bot.obter_dados_processo(
            numero_processo=challenge["numero_processo"],
            captcha_resposta=req.resposta,
            token_desafio=challenge["token_desafio"]
        )
        
        if resultado["status"] == "success":
            del ongoing_challenges[req.challenge_id]
            return resultado
            
        if resultado["status"] == "captcha_failed":
            new_id = resultado["challenge_id"]
            ongoing_challenges[new_id] = {
                "numero_processo": challenge["numero_processo"],
                "token_desafio": resultado["token_desafio"],
                "imagem_captcha_base64": resultado["imagem_captcha_base64"]
            }
            del ongoing_challenges[req.challenge_id]
            return resultado

        return resultado

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
