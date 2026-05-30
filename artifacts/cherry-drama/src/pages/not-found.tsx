import { Layout } from "@/components/layout";
import { Link } from "wouter";
import { Button } from "@/components/ui/button";
import { Film } from "lucide-react";

export default function NotFound() {
  return (
    <Layout>
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <Film className="h-16 w-16 text-primary/30 mx-auto mb-6" />
          <h1 className="text-5xl font-bold text-white mb-3 font-serif">404</h1>
          <p className="text-muted-foreground text-lg mb-8">This page doesn't exist.</p>
          <Button asChild>
            <Link href="/">Back to Upload</Link>
          </Button>
        </div>
      </div>
    </Layout>
  );
}
