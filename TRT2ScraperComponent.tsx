import React, { useState } from 'react';
import { Search, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button'; // Assumindo shadcn/ui Button
import { Input } from '@/components/ui/input';   // Assumindo shadcn/ui Input
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'; // Assumindo shadcn/ui Dialog
import { Label } from '@/components/ui/label';   // Assumindo shadcn/ui Label

// --- CONFIGURAÇÃO --- 
// Substitua pela URL do seu serviço no Easypanel (ex: https://trt2-bot.seuservidor.com)
// Esta URL deve ser acessível do frontend do JurisSync
const API_BASE_URL = "https://seu-dominio-do-easypanel.com"; 

export const TRT2ScraperComponent = () => {
  const [numeroProcesso, setNumeroProcesso] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processoData, setProcessoData] = useState<any>(null);
  const [captchaChallenge, setCaptchaChallenge] = useState<{challenge_id: string, imagem_captcha_base64: string} | null>(null);
  const [captchaInput, setCaptchaInput] = useState('');

  const handleConsultar = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    setProcessoData(null);
    setCaptchaChallenge(null);

    try {
      const response = await fetch(`${API_BASE_URL}/consultar_processo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero_processo: numeroProcesso }),
      });
      const data = await response.json();

      if (!response.ok) {
        // Erros HTTP (400, 500, etc.)
        throw new Error(data.detail || `Erro ${response.status}: ${response.statusText}`);
      }

      if (data.status === 'captcha_required') {
        setCaptchaChallenge(data);
      } else if (data.status === 'success') {
        setProcessoData(data.data); // A API retorna { status: 'success', data: {...} }
      } else {
        throw new Error('Resposta inesperada da API.');
      }
    } catch (err: any) {
      console.error("Erro na consulta:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResolverCaptcha = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/resolver_captcha`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          challenge_id: captchaChallenge?.challenge_id, 
          resposta: captchaInput 
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Erro ${response.status}: ${response.statusText}`);
      }

      if (data.status === 'success') {
        setProcessoData(data.data);
        setCaptchaChallenge(null);
        setCaptchaInput('');
      } else {
        throw new Error('Resposta inesperada da API ao resolver captcha.');
      }
    } catch (err: any) {
      console.error("Erro ao resolver captcha:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-card rounded-xl shadow-card p-6 border border-border">
        <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
          <Search className="w-6 h-6 text-primary" />
          Consulta TRT2 (PJe)
        </h2>
        
        <form onSubmit={handleConsultar} className="flex gap-3">
          <Input
            type="text"
            placeholder="0000000-00.0000.5.02.0000"
            className="flex-1"
            value={numeroProcesso}
            onChange={(e) => setNumeroProcesso(e.target.value)}
            disabled={loading}
          />
          <Button 
            type="submit"
            disabled={loading}
            className="bg-primary hover:bg-primary/90 text-primary-foreground px-6 py-2 font-medium flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Consultar'}
          </Button>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-destructive/10 border border-destructive text-destructive rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}
      </div>

      {/* Pop-up de Captcha (shadcn/ui Dialog) */}
      <Dialog open={!!captchaChallenge} onOpenChange={() => !loading && setCaptchaChallenge(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-foreground">Intervenção Necessária</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              O sistema do TRT2 solicita validação humana para o captcha.
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="flex justify-center bg-muted p-4 rounded-md border border-border">
              {captchaChallenge?.imagem_captcha_base64 && (
                <img 
                  src={`data:image/png;base64,${captchaChallenge.imagem_captcha_base64}`} 
                  alt="Captcha" 
                  className="h-16 rounded shadow-sm"
                />
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="captchaInput" className="text-right text-foreground">
                Digite os caracteres
              </Label>
              <Input
                id="captchaInput"
                autoFocus
                className="text-center text-2xl font-bold tracking-widest"
                value={captchaInput}
                onChange={(e) => setCaptchaInput(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>

          <DialogFooter>
            <Button 
              variant="outline"
              onClick={() => !loading && setCaptchaChallenge(null)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button 
              type="submit"
              onClick={handleResolverCaptcha}
              disabled={loading || !captchaInput}
              className="bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Validar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resultado */}
      {processoData && (
        <div className="bg-card rounded-xl shadow-card border border-border overflow-hidden animate-in slide-in-from-bottom-4 duration-300">
          <div className="bg-muted px-6 py-4 border-b border-border flex justify-between items-center">
            <h3 className="font-bold text-foreground">Dados do Processo</h3>
            <span className="bg-status-updated-bg text-status-updated-text px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Sincronizado
            </span>
          </div>
          <div className="p-6">
            <pre className="text-xs bg-slate-900 text-blue-400 p-4 rounded-lg overflow-x-auto">
              {JSON.stringify(processoData, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
