
import base64
import time
import uuid
from typing import Optional, Dict

import ddddocr
import requests

class TRT2Bot:
    def __init__(self, tribunal_url_base: str, api_key_2captcha: str):
        # Garante que a URL base termine corretamente para os endpoints
        self.tribunal_url_base = tribunal_url_base.rstrip('/')
        self.api_key_2captcha = api_key_2captcha
        # Inicializa o OCR local
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.session = requests.Session()

    def _resolver_captcha_2captcha(self, imagem_b64: str) -> Optional[str]:
        """
        Tenta resolver o captcha via 2Captcha se a chave estiver configurada.
        """
        if not self.api_key_2captcha or len(self.api_key_2captcha) < 10:
            return None
            
        print("[*] Tentando resolver captcha com 2Captcha...")
        try:
            # Enviar para 2Captcha
            res = self.session.post("http://2captcha.com/in.php", data={
                "key": self.api_key_2captcha,
                "method": "base64",
                "body": imagem_b64,
                "json": 1
            }, timeout=10)
            
            if res.json().get("status") == 1:
                request_id = res.json().get("request")
                # Aguardar resolução
                for _ in range(20):
                    time.sleep(5)
                    res_res = self.session.get(f"http://2captcha.com/res.php?key={self.api_key_2captcha}&action=get&id={request_id}&json=1")
                    if res_res.json().get("status") == 1:
                        return res_res.json().get("request")
            return None
        except Exception as e:
            print(f"[!] Erro no 2Captcha: {e}")
            return None

    def _resolver_captcha_ocr_local(self, imagem_b64: str) -> Optional[str]:
        """
        Tenta resolver o captcha usando OCR local (ddddocr).
        """
        try:
            img_bytes = base64.b64decode(imagem_b64)
            captcha_resposta = self.ocr.classification(img_bytes)
            print(f"[*] OCR local identificou: {captcha_resposta}")
            return captcha_resposta
        except Exception as e:
            print(f"[!] Erro no OCR local: {e}")
            return None

    def resolver_captcha_hibrido(self, imagem_b64: str) -> Optional[str]:
        """
        Estratégia híbrida: 2Captcha primeiro, depois OCR local 3 vezes.
        """
        # 1. Tenta 2Captcha
        resposta = self._resolver_captcha_2captcha(imagem_b64)
        if resposta:
            return resposta

        # 2. Tenta OCR local
        for i in range(3):
            print(f"[*] Tentativa {i+1} de OCR local...")
            resposta = self._resolver_captcha_ocr_local(imagem_b64)
            if resposta:
                return resposta
        return None

    def obter_dados_processo(self, numero_processo: str, captcha_resposta: Optional[str] = None, token_desafio: Optional[str] = None) -> Dict:
        """
        Fluxo principal de scraping do TRT2.
        """
        try:
            # Headers essenciais para evitar 403 Forbidden
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "X-Grau-Instancia": "1",
                "Referer": f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1"
            }

            # Passo 1: Obter ID interno do processo
            url_dados_basicos = f"{self.tribunal_url_base}/dadosbasicos/{numero_processo}"
            print(f"[*] Buscando ID: {url_dados_basicos}")
            response = self.session.get(url_dados_basicos, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            # TRT2 pode retornar lista ou objeto direto
            if isinstance(data, list) and len(data) > 0:
                processo_id = data[0].get("id")
            else:
                processo_id = data.get("id")
            
            if not processo_id:
                return {"status": "error", "message": "Processo não encontrado no tribunal."}

            # Passo 2: Obter Token de Desafio e Imagem do Captcha
            url_desafio = f"{self.tribunal_url_base}/{processo_id}"
            print(f"[*] Buscando desafio: {url_desafio}")
            response = self.session.get(url_desafio, headers=headers, timeout=15)
            response.raise_for_status()
            desafio_data = response.json()
            
            token_desafio_api = desafio_data.get("tokenDesafio")
            imagem_b64 = desafio_data.get("imagem") or desafio_data.get("imagemCaptcha")

            if not token_desafio_api or not imagem_b64:
                return {"status": "error", "message": "Falha ao obter desafio do captcha."}

            # Passo 3: Decidir entre Resolução Automática ou Humana
            if captcha_resposta and token_desafio:
                # Veio do endpoint /resolver_captcha
                print("[*] Usando resposta humana fornecida.")
                resposta_final = captcha_resposta
                token_a_validar = token_desafio
            else:
                # Tenta automático primeiro
                print("[*] Tentando resolução automática...")
                resposta_auto = self.resolver_captcha_hibrido(imagem_b64)
                if resposta_auto:
                    resposta_final = resposta_auto
                    token_a_validar = token_desafio_api
                else:
                    # Falhou automático -> Retorna para o Frontend solicitar ao usuário
                    print("[*] Requer intervenção humana.")
                    return {
                        "status": "captcha_required", 
                        "challenge_id": str(uuid.uuid4()), 
                        "imagem_captcha_base64": imagem_b64,
                        "token_desafio": token_desafio_api
                    }

            # Passo 4: Validar Captcha e obter Token de Sessão
            url_validar = f"{self.tribunal_url_base}/{processo_id}?tokenDesafio={token_a_validar}&resposta={resposta_final}"
            print(f"[*] Validando captcha...")
            response = self.session.get(url_validar, headers=headers, timeout=15)
            response.raise_for_status()

            captcha_token = response.headers.get("captchaToken")
            if not captcha_token:
                # Se falhar a validação, devolvemos como erro de captcha para nova tentativa
                return {
                    "status": "captcha_failed", 
                    "message": "Resposta do captcha incorreta.",
                    "challenge_id": str(uuid.uuid4()),
                    "imagem_captcha_base64": imagem_b64,
                    "token_desafio": token_desafio_api
                }

            # Passo 5: Buscar dados finais com o token de sessão
            print("[*] Buscando dados finais...")
            headers["captchaToken"] = captcha_token
            url_final = f"{self.tribunal_url_base}/{processo_id}"
            response = self.session.get(url_final, headers=headers, timeout=15)
            response.raise_for_status()

            return {"status": "success", "data": response.json()}

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                return {"status": "error", "message": "Acesso negado pelo tribunal (403). Verifique os headers."}
            return {"status": "error", "message": f"Erro HTTP: {e.response.status_code}"}
        except Exception as e:
            print(f"[!] Erro inesperado: {e}")
            return {"status": "error", "message": str(e)}
