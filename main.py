import base64
import time
import uuid
import os
import random
from typing import Optional, Dict
import ddddocr
from curl_cffi import requests

class TRT2Bot:
    def __init__(self, tribunal_url_base: str, api_key_2captcha: str):
        self.tribunal_url_base = tribunal_url_base.rstrip('/')
        self.api_key_2captcha = api_key_2captcha
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        
        # Configuração de Proxy via Variável de Ambiente (Opcional)
        self.proxy = os.getenv("PROXY_URL")
        
        # Inicializa a sessão com impersonate Chrome 120 para contornar o 403
        self.session = requests.Session(
            impersonate="chrome120",
            proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None
         )
        
    def _get_browser_headers(self):
        """Headers de nível de navegador (Client Hints) para simular Windows Real"""
        return {
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _preparar_sessao(self, numero_processo: str):
        """Simula a entrada do usuário para gerar cookies reais"""
        url_portal = f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1"
        try:
            # Visita inicial para estabelecer identidade
            self.session.get("https://pje.trt2.jus.br/consultaprocessual/", headers=self._get_browser_headers( ), timeout=30)
            time.sleep(random.uniform(1.0, 2.0))
            # Visita a página do processo
            self.session.get(url_portal, headers=self._get_browser_headers(), timeout=30)
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"[*] Erro ao preparar sessão: {e}")

    def _get_api_headers(self, numero_processo: str):
        """Headers exatos para a API do PJe"""
        headers = self._get_browser_headers()
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://pje.trt2.jus.br",
            "Referer": f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Grau-Instancia": "1"
        } )
        # Remove headers que o Chrome não envia em XHR
        headers.pop("Upgrade-Insecure-Requests", None)
        headers.pop("Sec-Fetch-User", None)
        return headers

    def obter_dados_processo(self, numero_processo: str, captcha_resposta: Optional[str] = None, token_desafio: Optional[str] = None) -> Dict:
        try:
            # Se não for resolução de captcha, prepara uma nova sessão
            if not captcha_resposta:
                self._preparar_sessao(numero_processo)
            
            headers = self._get_api_headers(numero_processo)

            # 1. Obter ID interno (Dados Básicos)
            url_id = f"{self.tribunal_url_base}/dadosbasicos/{numero_processo}"
            response = self.session.get(url_id, headers=headers, timeout=25)
            
            if response.status_code == 403:
                return {"status": "error", "message": "Bloqueio 403: O IP do servidor pode estar marcado. Considere usar PROXY_URL."}
            
            response.raise_for_status()
            data = response.json()
            processo_id = data[0].get("id") if isinstance(data, list) and data else data.get("id")
            
            if not processo_id:
                return {"status": "error", "message": "Processo não encontrado no TRT2."}

            # 2. Obter Desafio de Captcha
            url_desafio = f"{self.tribunal_url_base}/{processo_id}"
            response = self.session.get(url_desafio, headers=headers, timeout=25)
            response.raise_for_status()
            desafio_data = response.json()
            
            token_desafio_api = desafio_data.get("tokenDesafio")
            imagem_b64 = desafio_data.get("imagem") or desafio_data.get("imagemCaptcha")

            # 3. Validar Captcha (se a resposta foi enviada)
            if captcha_resposta and token_desafio:
                url_validar = f"{self.tribunal_url_base}/{processo_id}?tokenDesafio={token_desafio}&resposta={captcha_resposta}"
                response = self.session.get(url_validar, headers=headers, timeout=25)
                
                captcha_token = response.headers.get("captchaToken")
                if not captcha_token:
                    return {
                        "status": "captcha_failed", 
                        "message": "Captcha incorreto.",
                        "challenge_id": str(uuid.uuid4()),
                        "imagem_captcha_base64": imagem_b64,
                        "token_desafio": token_desafio_api
                    }

                # 4. Buscar Dados Finais com o token validado
                headers["captchaToken"] = captcha_token
                url_final = f"{self.tribunal_url_base}/{processo_id}"
                response = self.session.get(url_final, headers=headers, timeout=25)
                return {"status": "success", "data": response.json()}

            else:
                # Retorna o desafio para o frontend resolver
                return {
                    "status": "captcha_required", 
                    "challenge_id": str(uuid.uuid4()), 
                    "imagem_captcha_base64": imagem_b64,
                    "token_desafio": token_desafio_api
                }

        except Exception as e:
            return {"status": "error", "message": f"Erro de Conexão: {str(e)}"}
