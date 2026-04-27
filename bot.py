
import base64
import time
import uuid
from typing import Optional, Dict

import ddddocr
import requests

class TRT2Bot:
    def __init__(self, tribunal_url_base: str, api_key_2captcha: str):
        self.tribunal_url_base = tribunal_url_base
        self.api_key_2captcha = api_key_2captcha
        self.ocr = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)

    def _resolver_captcha_2captcha(self, imagem_b64: str) -> Optional[str]:
        # Implementação fictícia para 2Captcha
        # Em um cenário real, você faria uma requisição para a API do 2Captcha aqui
        print("Tentando resolver captcha com 2Captcha...")
        # Simula um atraso e um resultado
        time.sleep(2)
        # Retorna None para simular falha ou um valor para sucesso
        return None # Simula falha para forçar OCR local

    def _resolver_captcha_ocr_local(self, imagem_b64: str) -> Optional[str]:
        try:
            img_bytes = base64.b64decode(imagem_b64)
            captcha_resposta = self.ocr.classification(img_bytes)
            print(f"OCR local tentou resolver captcha: {captcha_resposta}")
            return captcha_resposta
        except Exception as e:
            print(f"Erro no OCR local: {e}")
            return None

    def resolver_captcha_hibrido(self, imagem_b64: str) -> Optional[str]:
        # Tenta 2Captcha primeiro
        resposta_2captcha = self._resolver_captcha_2captcha(imagem_b64)
        if resposta_2captcha:
            return resposta_2captcha

        # Se 2Captcha falhar, tenta OCR local 3 vezes
        for i in range(3):
            print(f"Tentativa {i+1} de OCR local...")
            resposta_ocr = self._resolver_captcha_ocr_local(imagem_b64)
            if resposta_ocr:
                return resposta_ocr
        return None

    def obter_dados_processo(self, numero_processo: str, captcha_resposta: Optional[str] = None, token_desafio: Optional[str] = None) -> Dict:
        processo_id = None
        imagem_b64 = None # Inicializa imagem_b64 aqui para garantir acessibilidade

        try:
            # Passo 1: Obter ID interno do processo
            response = requests.get(f"{self.tribunal_url_base}/dadosbasicos/{numero_processo}")
            response.raise_for_status()
            processo_id = response.json().get("id")

            if not processo_id:
                return {"status": "error", "message": "ID do processo não encontrado."}

            # Passo 2: Obter tokenDesafio e imagem do captcha
            response = requests.get(f"{self.tribunal_url_base}/processos/{processo_id}")
            response.raise_for_status()
            data = response.json()
            token_desafio_api = data.get("tokenDesafio")
            imagem_b64 = data.get("imagemCaptcha")

            if not token_desafio_api or not imagem_b64:
                return {"status": "error", "message": "Token de desafio ou imagem do captcha não recebidos."}

            # Se já temos a resposta do captcha (do /resolver_captcha), usamos ela
            if captcha_resposta and token_desafio:
                print("Usando resposta de captcha fornecida pelo usuário.")
                resposta_final_captcha = captcha_resposta
                token_desafio_a_usar = token_desafio
            else:
                # Tenta resolver o captcha automaticamente
                print("Tentando resolver captcha automaticamente...")
                resposta_automatica = self.resolver_captcha_hibrido(imagem_b64)

                if resposta_automatica:
                    print(f"Captcha resolvido automaticamente: {resposta_automatica}")
                    resposta_final_captcha = resposta_automatica
                    token_desafio_a_usar = token_desafio_api
                else:
                    print("Resolução automática do captcha falhou. Requer intervenção humana.")
                    return {"status": "captcha_required", "challenge_id": str(uuid.uuid4()), "imagem_captcha_base64": imagem_b64}

            # Passo 5a: Validar captcha e obter captchaToken
            validation_url = f"{self.tribunal_url_base}/processos/{processo_id}?tokenDesafio={token_desafio_a_usar}&resposta={resposta_final_captcha}"
            response = requests.get(validation_url)
            response.raise_for_status()

            captcha_token = response.headers.get("captchaToken")
            if not captcha_token:
                # Se a validação falhar, e não foi uma resposta humana, tenta novamente como captcha_required
                if not (captcha_resposta and token_desafio):
                    print("Validação automática do captcha falhou. Requer intervenção humana.")
                    return {"status": "captcha_required", "challenge_id": str(uuid.uuid4()), "imagem_captcha_base64": imagem_b64}
                else:
                    return {"status": "captcha_failed", "message": "Resposta do captcha incorreta.", "challenge_id": str(uuid.uuid4()), "imagem_captcha_base64": imagem_b64}

            # Passo 5a (continuação): Buscar dados finais com captchaToken
            final_data_url = f"{self.tribunal_url_base}/processos/{processo_id}"
            headers = {"captchaToken": captcha_token}
            response = requests.get(final_data_url, headers=headers)
            response.raise_for_status()

            return {"status": "success", "data": response.json()}

        except requests.exceptions.RequestException as e:
            print(f"Erro de requisição: {e}")
            return {"status": "error", "message": f"Erro de comunicação com o tribunal: {e}"}
        except Exception as e:
            print(f"Erro inesperado: {e}")
            return {"status": "error", "message": f"Erro inesperado: {e}"}

