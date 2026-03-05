import { useState } from 'react';
import { GitBranch, Loader2 } from 'lucide-react';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { cn } from '@/utils/cn';

interface CloneFormProps {
  onClone: (url: string) => void;
  loading: boolean;
}

export function CloneForm({ onClone, loading }: CloneFormProps) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!url.trim()) {
      setError('Please enter a repository URL');
      return;
    }
    onClone(url.trim());
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <GitBranch className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="https://github.com/username/repository"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className={cn("pl-10 h-12", error && "border-destructive")}
              disabled={loading}
            />
          </div>
          <Button type="submit" disabled={loading} className="h-12 px-8">
            {loading ? (
              <><Loader2 className="mr-2 h-5 w-5 animate-spin" />Cloning...</>
            ) : (
              <><GitBranch className="mr-2 h-5 w-5" />Clone</>
            )}
          </Button>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </form>
    </div>
  );
}
