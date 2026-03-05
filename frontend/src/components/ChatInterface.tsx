import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, AlertCircle } from 'lucide-react';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { cn } from '@/utils/cn';
import type { ChatMessage } from '@/types';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  loading: boolean;
  agentName: string;
}

export function ChatInterface({ messages, onSendMessage, loading, agentName }: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  return (
    <div className="flex flex-col h-full border rounded-lg bg-card">
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <Bot className="h-5 w-5 text-primary" />
        <span className="font-medium">Chat with {agentName}</span>
      </div>

      <div ref={scrollRef} className="flex-1 p-4 space-y-4 overflow-auto min-h-[400px] max-h-[500px]">
        {messages.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Bot className="mx-auto h-12 w-12 mb-4 opacity-50" />
            <p>Start a conversation with the agent</p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={cn("flex gap-3 mb-4 animate-fade-in", message.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
            >
              <div className={cn("w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0", message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-secondary')}>
                {message.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              <div className={cn("max-w-[80%] rounded-lg px-4 py-2", message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted')}>
                {message.error ? (
                  <div className="flex items-start gap-2 text-destructive">
                    <AlertCircle className="h-4 w-4 mt-0.5" />
                    <span>{message.content}</span>
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap">{message.content}</div>
                )}
                {message.files && message.files.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-border/50">
                    <p className="text-xs opacity-70 mb-1">Generated files:</p>
                    <div className="flex flex-wrap gap-1">
                      {message.files.map((file, idx) => (
                        <span key={idx} className="text-xs px-2 py-0.5 rounded bg-background/50">{file}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center"><Bot className="h-4 w-4" /></div>
            <div className="bg-muted rounded-lg px-4 py-3 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm text-muted-foreground">Thinking...</span>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex gap-2">
          <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your message..." disabled={loading} className="flex-1" />
          <Button type="submit" disabled={loading || !input.trim()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </form>
    </div>
  );
}
