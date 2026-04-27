
import base64
import time
import uuid
from typing import Optional, Dict
import ddddocr
import requests

class TRT2Bot:
    def __init__(self, tribunal_url_base: str, api_key_2captcha: str):
        self.tribunal_url_base = tribunal_url_base.rstrip('/')
        self.api_key_2captcha = api_key_2captcha
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.session = requests.Session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    def _get_headers(self, numero_processo: str):
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "X-Grau-Instancia": "1",
            "Referer": f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1",
            "Origin": "https://pje.trt2.jus.br"
        }

    def _resolver_captcha_ocr_local(self, imagem_b64: str) -> Optional[str]:
        try:
            img_bytes = base64.b64decode(imagem_b64)
            return self.ocr.classification(img_bytes)
        except Exception:
            return None

    def obter_dados_processo(self, numero_processo: str, captcha_resposta: Optional[str] = None, token_desafio: Optional[str] = None) -> Dict:
        try:
            headers = self._get_headers(numero_processo)
            
            # 1. Visita inicial para simular fluxo humano
            self.session.get(f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1", headers={"User-Agent": self.user_agent})

            # 2. Obter ID interno
            url_id = f"{self.tribunal_url_base}/dadosbasicos/{numero_processo}"
            print(f"[*] Chamando: {url_id}")
            response = self.session.get(url_id, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            processo_id = data[0].get("id") if isinstance(data, list) and data else data.get("id")
            if not processo_id:
                return {"status": "error", "message": "Processo não encontrado."}

            # 3. Obter Desafio
            url_desafio = f"{self.tribunal_url_base}/{processo_id}"
            response = self.session.get(url_desafio, headers=headers, timeout=15)
            response.raise_for_status()
            desafio_data = response.json()
            
            token_desafio_api = desafio_data.get("tokenDesafio")
            imagem_b64 = desafio_data.get("imagem") or desafio_data.get("imagemCaptcha")

            if captcha_resposta and token_desafio:
                resposta_final = captcha_resposta
                token_a_validar = token_desafio
            else:
                # Tenta OCR local
                resposta_auto = self._resolver_captcha_ocr_local(imagem_b64)
                # Para garantir que o usuário veja o captcha se o OCR for incerto, 
                # vamos sempre retornar captcha_required neste teste manual
                return {
                    "status": "captcha_required", 
                    "challenge_id": str(uuid.uuid4()), 
                    "imagem_captcha_base64": imagem_b64,
                    "token_desafio": token_desafio_api
                }

            # 4. Validar
            url_validar = f"{self.tribunal_url_base}/{processo_id}?tokenDesafio={token_a_validar}&resposta={resposta_final}"
            response = self.session.get(url_validar, headers=headers, timeout=15)
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

            # 5. Final
            headers["captchaToken"] = captcha_token
            url_final = f"{self.tribunal_url_base}/{processo_id}"
            response = self.session.get(url_final, headers=headers, timeout=15)
            response.raise_for_status()

            return {"status": "success", "data": response.json()}

        except requests.exceptions.HTTPError as e:
            return {"status": "error", "message": f"Erro {e.response.status_code} no tribunal. Verifique os headers."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
