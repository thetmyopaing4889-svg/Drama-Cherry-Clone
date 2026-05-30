import { useState, useEffect } from "react";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Eye, EyeOff, Save, ShieldCheck } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const KEYS = {
  groq: "GROQ_API_KEY",
  gemini: "GEMINI_API_KEY",
} as const;

function ApiKeyField({ label, storageKey, description }: { label: string; storageKey: string; description: string }) {
  const [value, setValue] = useState("");
  const [show, setShow] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setValue(localStorage.getItem(storageKey) ?? "");
  }, [storageKey]);

  const save = () => {
    if (value.trim()) {
      localStorage.setItem(storageKey, value.trim());
    } else {
      localStorage.removeItem(storageKey);
    }
    toast({ title: "Saved", description: `${label} updated in browser storage.` });
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium text-white">{label}</Label>
      <p className="text-xs text-muted-foreground">{description}</p>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Input
            type={show ? "text" : "password"}
            value={value}
            onChange={e => setValue(e.target.value)}
            placeholder="Enter API key..."
            className="bg-background/50 pr-10"
          />
          <button
            type="button"
            onClick={() => setShow(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-white transition-colors"
          >
            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        <Button size="sm" onClick={save} className="shrink-0">
          <Save className="h-4 w-4 mr-1.5" />
          Save
        </Button>
      </div>
      {localStorage.getItem(storageKey) && (
        <p className="text-xs text-green-400 flex items-center gap-1">
          <ShieldCheck className="h-3 w-3" /> Key saved in browser
        </p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Layout>
      <div className="max-w-2xl mx-auto w-full p-8 pt-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2 font-serif tracking-wide">Settings</h1>
          <p className="text-muted-foreground">Manage your API keys and channel preferences.</p>
        </div>

        <div className="mb-6 p-4 rounded-xl bg-amber-900/20 border border-amber-600/30 text-amber-300 text-sm flex gap-3">
          <ShieldCheck className="h-5 w-5 shrink-0 mt-0.5" />
          <div>
            <strong>Privacy notice:</strong> API keys are stored only in your browser's localStorage. They are never sent to or stored on our server.
          </div>
        </div>

        <div className="flex items-center gap-4 mb-8 p-4 bg-card/40 rounded-xl border border-border">
          <img src={`${import.meta.env.BASE_URL}cherry-drama-logo.jpg`} alt="Cherry Drama" className="h-16 w-16 rounded-xl object-cover border border-primary/30" onError={e => { (e.target as HTMLImageElement).style.display='none'; }} />
          <div>
            <div className="font-bold text-white text-lg">Cherry Drama</div>
            <div className="text-sm text-muted-foreground">Myanmar &amp; Japanese Drama Recap Channel</div>
          </div>
        </div>

        <Card className="bg-card/50 border-border">
          <CardHeader>
            <CardTitle>API Keys</CardTitle>
            <CardDescription>Required for the AI processing pipeline to work.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <ApiKeyField
              label="Groq API Key"
              storageKey={KEYS.groq}
              description="Used for Whisper transcription. Get yours at console.groq.com"
            />
            <div className="border-t border-border" />
            <ApiKeyField
              label="Gemini API Key"
              storageKey={KEYS.gemini}
              description="Used for scene analysis and recap script generation. Get yours at aistudio.google.com"
            />
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
