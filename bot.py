import requests
import base64
import json
import time
import os
import ddddocr

class TRT2Bot:
    def __init__(self, api_key_2captcha: str = None, tribunal_url_base: str = "https://pje.trt2.jus.br/pje-consulta-api/api/processos"):
        self.url_base = tribunal_url_base
        self.session = requests.Session()
        self.api_key_2captcha = api_key_2captcha if api_key_2captcha else os.getenv("API_KEY_2CAPTCHA")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "X-Grau-Instancia": "1",
            "Content-Type": "application/json"
        }
        # Inicializa o OCR local apenas uma vez
        self.ocr_local = ddddocr.DdddOcr(show_ad=False) if ddddocr else None

    def _resolver_captcha_2captcha(self, imagem_b64: str) -> Optional[str]:
        if not self.api_key_2captcha:
            return None
        try:
            post_res = requests.post("http://2captcha.com/in.php", data={
                'key': self.api_key_2captcha, 'method': 'base64', 'body': imagem_b64, 'json': 1
            }, timeout=10)
            res_json = post_res.json()
            
            if res_json.get('status') == 1:
                request_id = res_json.get('request')
                for _ in range(10): # Tenta 10 vezes com intervalo de 5 segundos
                    time.sleep(5)
                    get_res = requests.get(f"http://2captcha.com/res.php?key={self.api_key_2captcha}&action=get&id={request_id}&json=1")
                    get_json = get_res.json()
                    if get_json.get('status') == 1:
                        return get_json.get('request') # Retorna a resposta do captcha
                    elif get_json.get('request') == 'CAPCHA_NOT_READY':
                        continue
                    else: # Outros erros do 2Captcha
                        print(f"Erro 2Captcha: {get_json.get('request')}")
                        return None
            else: # Erro ao enviar o captcha
                print(f"Erro ao enviar captcha para 2Captcha: {res_json.get('request')}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão com 2Captcha: {e}")
            return None
        except Exception as e:
            print(f"Erro inesperado no 2Captcha: {e}")
            return None
        return None

    def _resolver_captcha_ocr_local(self, imagem_b64: str) -> Optional[str]:
        if not self.ocr_local:
            return None
        try:
            img_bytes = base64.b64decode(imagem_b64)
            return self.ocr_local.classification(img_bytes)
        except Exception as e:
            print(f"Erro OCR local: {e}")
            return None

    def resolver_captcha_hibrido(self, imagem_b64: str) -> Optional[str]:
        # 1. Tenta 2Captcha
        print("Tentando resolver captcha via 2Captcha...")
        resposta = self._resolver_captcha_2captcha(imagem_b64)
        if resposta:
            print(f"2Captcha resolveu: {resposta}")
            return resposta

        # 2. Fallback para OCR local (com múltiplas tentativas)
        print("2Captcha falhou ou não configurado. Tentando OCR local...")
        for i in range(3): # Tenta OCR local 3 vezes
            resposta_ocr = self._resolver_captcha_ocr_local(imagem_b64)
            if resposta_ocr:
                print(f"OCR local tentou ({i+1}/3): {resposta_ocr}")
                return resposta_ocr
            time.sleep(1) # Pequeno delay entre tentativas
        print("OCR local falhou após múltiplas tentativas.")
        return None

    def obter_dados_processo(self, numero_processo: str, captcha_resposta: Optional[str] = None, token_desafio: Optional[str] = None, processo_id: Optional[str] = None) -> Dict:
        # 1. Obter ID do processo e token de desafio (se não tiver)
        if not processo_id or not token_desafio:
            print(f"[*] Buscando ID e desafio para: {numero_processo}")
            self.headers["Referer"] = f"https://pje.trt2.jus.br/consultaprocessual/detalhe-processo/{numero_processo}/1"
            
            res_dados = self.session.get(f"{self.url_base}/dadosbasicos/{numero_processo}", headers=self.headers, timeout=15)
            res_dados.raise_for_status() # Levanta exceção para erros HTTP
            
            data = res_dados.json()
            processo_id = data[0].get("id") if isinstance(data, list) else data.get("id")
            
            res_desafio = self.session.get(f"{self.url_base}/{processo_id}", headers=self.headers, timeout=15)
            res_desafio.raise_for_status()
            desafio_data = res_desafio.json()
            
            token_desafio = desafio_data.get('tokenDesafio')
            imagem_b64 = desafio_data.get('imagem')

            if not token_desafio or not imagem_b64:
                raise Exception("Não foi possível obter token de desafio ou imagem do captcha.")

            # Se não há resposta de captcha, tenta resolver automaticamente
            if not captcha_resposta:
                captcha_resposta = self.resolver_captcha_hibrido(imagem_b64)
                if not captcha_resposta:
                    # Se a resolução automática falhou, retorna os dados para intervenção humana
                    return {
                        "status": "captcha_required",
                        "processo_id": str(processo_id),
                        "token_desafio": token_desafio,
                        "imagem_captcha_base64": imagem_b64
                    }
        
        # 2. Validar o captcha e obter o captchaToken
        print(f"[*] Validando captcha com resposta: {captcha_resposta}")
        url_valida = f"{self.url_base}/{processo_id}?tokenDesafio={token_desafio}&resposta={captcha_resposta}"
        res_valida = self.session.get(url_valida, headers=self.headers, timeout=15)
        res_valida.raise_for_status()
        
        captcha_token = res_valida.headers.get('captchatoken')
        if not captcha_token:
            # Se não veio captchaToken, a resposta do captcha estava errada
            return {"status": "captcha_failed", "message": "Resposta do captcha incorreta ou expirada."}

        # 3. Obter os dados finais do processo
        print(f"[*] Captcha validado. Buscando dados finais com captchaToken: {captcha_token}")
        res_final = self.session.get(f"{self.url_base}/{processo_id}?tokenCaptcha={captcha_token}", headers=self.headers, timeout=15)
        res_final.raise_for_status()
        
        return {"status": "success", "data": res_final.json()}


# Exemplo de uso (para testes locais)
if __name__ == "__main__":
    bot = TRT2Bot(api_key_2captcha=os.getenv("API_KEY_2CAPTCHA")) # Pega a chave da variável de ambiente
    processo_exemplo = "1000435-34.2022.5.02.0315"

    try:
        resultado = bot.obter_dados_processo(processo_exemplo)
        if resultado.get("status") == "captcha_required":
            print("\n--- INTERVENÇÃO HUMANA NECESSÁRIA ---")
            print("Captcha para o processo:", processo_exemplo)
            # Salvar imagem para o usuário ver
            with open("captcha_para_resolver.png", "wb") as f:
                f.write(base64.b64decode(resultado["imagem_captcha_base64"]))
            print("Imagem salva como captcha_para_resolver.png. Por favor, resolva.")
            resposta_humana = input("Digite a resposta do captcha: ")
            
            # Tentar novamente com a resposta humana
            resultado_final = bot.obter_dados_processo(
                numero_processo=processo_exemplo,
                captcha_resposta=resposta_humana,
                token_desafio=resultado["token_desafio"],
                processo_id=resultado["processo_id"]
            )
            print("Resultado final:", json.dumps(resultado_final, indent=2))
        else:
            print("Resultado direto:", json.dumps(resultado, indent=2))
    except Exception as e:
        print(f"Erro ao obter processo: {e}")
