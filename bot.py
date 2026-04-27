
import base64
import time
import uuid
from typing import Optional, Dict
import ddddocr
from curl_cffi import requests

class TRT2Bot:
    def __init__(self, tribunal_url_base: str, api_key_2captcha: str):
        self.tribunal_url_base = tribunal_url_base.rstrip('/')
        self.api_key_2captcha = api_key_2captcha
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        # O segredo do Manus: Impersonate Chrome 120 com Session persistente
        self.session = requests.Session(impersonate="chrome120")
        
    def _preparar_sessao(self, numero_processo: str):
        """Simula a entrada do usuário na página de consulta para gerar cookies reais"""
        url_portal = f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        try:
            self.session.get(url_portal, headers=headers, timeout=20)
            time.sleep(1) # Delay humano
        except Exception as e:
            print(f"[*] Erro ao preparar sessão: {e}")

    def _get_api_headers(self, numero_processo: str):
        """Headers exatos que o Chrome envia para a API do PJe"""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": "https://pje.trt2.jus.br",
            "Referer": f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Grau-Instancia": "1"
        }

    def _resolver_captcha_2captcha(self, imagem_b64: str) -> Optional[str]:
        if not self.api_key_2captcha or len(self.api_key_2captcha) < 10:
            return None
        try:
            # Para o 2Captcha usamos requests normal para não misturar sessões
            import requests as req_normal
            res = req_normal.post("http://2captcha.com/in.php", data={
                "key": self.api_key_2captcha,
                "method": "base64",
                "body": imagem_b64,
                "json": 1
            }, timeout=10)
            if res.json().get("status") == 1:
                request_id = res.json().get("request")
                for _ in range(20):
                    time.sleep(5)
                    res_res = req_normal.get(f"http://2captcha.com/res.php?key={self.api_key_2captcha}&action=get&id={request_id}&json=1")
                    if res_res.json().get("status") == 1:
                        return res_res.json().get("request")
            return None
        except Exception:
            return None

    def obter_dados_processo(self, numero_processo: str, captcha_resposta: Optional[str] = None, token_desafio: Optional[str] = None) -> Dict:
        try:
            # 1. Preparar Sessão (Cookies)
            if not captcha_resposta:
                self._preparar_sessao(numero_processo)
            
            headers = self._get_api_headers(numero_processo)

            # 2. Obter ID interno
            url_id = f"{self.tribunal_url_base}/dadosbasicos/{numero_processo}"
            print(f"[*] API Dados Básicos: {url_id}")
            response = self.session.get(url_id, headers=headers, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            processo_id = data[0].get("id") if isinstance(data, list) and data else data.get("id")
            if not processo_id:
                return {"status": "error", "message": "Processo não encontrado no TRT2."}

            # 3. Obter Desafio de Captcha
            url_desafio = f"{self.tribunal_url_base}/{processo_id}"
            response = self.session.get(url_desafio, headers=headers, timeout=20)
            response.raise_for_status()
            desafio_data = response.json()
            
            token_desafio_api = desafio_data.get("tokenDesafio")
            imagem_b64 = desafio_data.get("imagem") or desafio_data.get("imagemCaptcha")

            # 4. Resolver Captcha (Humano ou Automático)
            if captcha_resposta and token_desafio:
                resposta_final = captcha_resposta
                token_a_validar = token_desafio
            else:
                resposta_auto = self._resolver_captcha_2captcha(imagem_b64)
                if not resposta_auto:
                    return {
                        "status": "captcha_required", 
                        "challenge_id": str(uuid.uuid4()), 
                        "imagem_captcha_base64": imagem_b64,
                        "token_desafio": token_desafio_api
                    }
                resposta_final = resposta_auto
                token_a_validar = token_desafio_api

            # 5. Validar Captcha
            url_validar = f"{self.tribunal_url_base}/{processo_id}?tokenDesafio={token_a_validar}&resposta={resposta_final}"
            response = self.session.get(url_validar, headers=headers, timeout=20)
            response.raise_for_status()

            captcha_token = response.headers.get("captchaToken")
            if not captcha_token:
                return {
                    "status": "captcha_failed", 
                    "message": "Captcha incorreto.",
                    "challenge_id": str(uuid.uuid4()),
                    "imagem_captcha_base64": imagem_b64,
                    "token_desafio": token_desafio_api
                }

            # 6. Buscar Dados Finais
            headers["captchaToken"] = captcha_token
            url_final = f"{self.tribunal_url_base}/{processo_id}"
            response = self.session.get(url_final, headers=headers, timeout=20)
            response.raise_for_status()

            return {"status": "success", "data": response.json()}

        except Exception as e:
            return {"status": "error", "message": f"Erro de Conexão: {str(e)}"}
