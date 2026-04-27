
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
        self.impersonate = "chrome120"

    def _get_headers(self, numero_processo: str):
        return {
            "Accept": "application/json, text/plain, */*",
            "X-Grau-Instancia": "1",
            "Referer": f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1",
            "Origin": "https://pje.trt2.jus.br"
        }

    def _resolver_captcha_2captcha(self, imagem_b64: str) -> Optional[str]:
        if not self.api_key_2captcha or len(self.api_key_2captcha) < 10:
            return None
        try:
            res = requests.post("http://2captcha.com/in.php", data={
                "key": self.api_key_2captcha,
                "method": "base64",
                "body": imagem_b64,
                "json": 1
            }, timeout=10)
            if res.json().get("status") == 1:
                request_id = res.json().get("request")
                for _ in range(20):
                    time.sleep(5)
                    res_res = requests.get(f"http://2captcha.com/res.php?key={self.api_key_2captcha}&action=get&id={request_id}&json=1")
                    if res_res.json().get("status") == 1:
                        return res_res.json().get("request")
            return None
        except Exception:
            return None

    def _resolver_captcha_ocr_local(self, imagem_b64: str) -> Optional[str]:
        try:
            img_bytes = base64.b64decode(imagem_b64)
            return self.ocr.classification(img_bytes)
        except Exception:
            return None

    def obter_dados_processo(self, numero_processo: str, captcha_resposta: Optional[str] = None, token_desafio: Optional[str] = None) -> Dict:
        try:
            headers = self._get_headers(numero_processo)
            
            # 1. Obter ID interno usando curl_cffi para imitar o Chrome
            url_id = f"{self.tribunal_url_base}/dadosbasicos/{numero_processo}"
            print(f"[*] Chamando: {url_id}")
            response = requests.get(url_id, headers=headers, impersonate=self.impersonate, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            processo_id = data[0].get("id") if isinstance(data, list) and data else data.get("id")
            if not processo_id:
                return {"status": "error", "message": "Processo não encontrado."}

            # 2. Obter Desafio
            url_desafio = f"{self.tribunal_url_base}/{processo_id}"
            response = requests.get(url_desafio, headers=headers, impersonate=self.impersonate, timeout=15)
            response.raise_for_status()
            desafio_data = response.json()
            
            token_desafio_api = desafio_data.get("tokenDesafio")
            imagem_b64 = desafio_data.get("imagem") or desafio_data.get("imagemCaptcha")

            if captcha_resposta and token_desafio:
                resposta_final = captcha_resposta
                token_a_validar = token_desafio
            else:
                # Tenta 2Captcha se configurado
                resposta_auto = self._resolver_captcha_2captcha(imagem_b64)
                if not resposta_auto:
                    # Se não tiver 2Captcha ou falhar, retorna para intervenção humana
                    return {
                        "status": "captcha_required", 
                        "challenge_id": str(uuid.uuid4()), 
                        "imagem_captcha_base64": imagem_b64,
                        "token_desafio": token_desafio_api
                    }
                resposta_final = resposta_auto
                token_a_validar = token_desafio_api

            # 3. Validar Captcha
            url_validar = f"{self.tribunal_url_base}/{processo_id}?tokenDesafio={token_a_validar}&resposta={resposta_final}"
            response = requests.get(url_validar, headers=headers, impersonate=self.impersonate, timeout=15)
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

            # 4. Obter Dados Finais
            headers["captchaToken"] = captcha_token
            url_final = f"{self.tribunal_url_base}/{processo_id}"
            response = requests.get(url_final, headers=headers, impersonate=self.impersonate, timeout=15)
            response.raise_for_status()

            return {"status": "success", "data": response.json()}

        except Exception as e:
            return {"status": "error", "message": str(e)}
