import { useState, useCallback } from 'react';
import { Header } from './components/Header';
import { CloneForm } from './components/CloneForm';
import { AgentGrid } from './components/AgentGrid';
import { ChatInterface } from './components/ChatInterface';
import { FileExplorer } from './components/FileExplorer';
import { Button } from './components/ui/Button';
import { useCloneRepository, useChat, useGetFiles, useDownload, useDeleteSession } from './hooks/useApi';
import type { Agent, ChatMessage, FileInfo } from './types';
import { Loader2, Trash2 } from 'lucide-react';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [files, setFiles] = useState<FileInfo[]>([]);

  const { clone, loading: cloning, error: cloneError } = useCloneRepository();
  const { sendMessage, loading: chatting } = useChat();
  const { getFiles } = useGetFiles();
  const { download, loading: downloading } = useDownload();
  const { deleteSession } = useDeleteSession();

  const handleClone = useCallback(async (repoUrl: string) => {
    try {
      const response = await clone(repoUrl);
      setSessionId(response.sessionId);
      setAgents(response.agents);
      setSelectedAgent(null);
      setMessages([]);
      setFiles([]);
    } catch (error) {
      console.error('Clone failed:', error);
    }
  }, [clone]);

  const handleSelectAgent = useCallback((agent: Agent) => {
    setSelectedAgent(agent);
    setMessages([]);
  }, []);

  const handleSendMessage = useCallback(async (message: string) => {
    if (!sessionId || !selectedAgent) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      const response = await sendMessage(sessionId, selectedAgent.id, message);

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        files: response.files,
        error: response.error,
      };
      setMessages(prev => [...prev, assistantMessage]);

      if (response.files.length > 0) {
        const fileData = await getFiles(sessionId);
        setFiles(fileData);
      }
    } catch (error) {
      console.error('Chat failed:', error);
    }
  }, [sessionId, selectedAgent, sendMessage, getFiles]);

  const handleDownload = useCallback(async () => {
    if (!sessionId) return;
    await download(sessionId);
  }, [sessionId, download]);

  const handleReset = useCallback(async () => {
    if (sessionId) {
      try {
        await deleteSession(sessionId);
      } catch (error) {
        console.error('Delete failed:', error);
      }
    }
    setSessionId(null);
    setAgents([]);
    setSelectedAgent(null);
    setMessages([]);
    setFiles([]);
  }, [sessionId, deleteSession]);

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container mx-auto px-4 py-8">
        <section className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl font-bold">Clone Repository</h2>
              <p className="text-muted-foreground">Enter a Git repository URL to clone and detect AI agents</p>
            </div>
            {sessionId && (
              <Button variant="outline" onClick={handleReset} className="gap-2">
                <Trash2 className="h-4 w-4" />
                New Session
              </Button>
            )}
          </div>

          <CloneForm onClone={handleClone} loading={cloning} />

          {cloneError && <p className="mt-4 text-sm text-destructive">{cloneError}</p>}

          {sessionId && (
            <div className="mt-4 p-3 bg-muted rounded-lg">
              <p className="text-sm"><span className="font-medium">Session ID:</span> <code className="bg-background px-2 py-0.5 rounded">{sessionId}</code></p>
            </div>
          )}
        </section>

        {sessionId && agents.length > 0 && (
          <section className="mb-8 animate-fade-in">
            <h2 className="text-2xl font-bold mb-4">Detected Agents</h2>
            <AgentGrid agents={agents} selectedAgent={selectedAgent} onSelectAgent={handleSelectAgent} />
          </section>
        )}

        {selectedAgent && (
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">
            <div>
              <h2 className="text-xl font-bold mb-4">Chat</h2>
              <ChatInterface
                messages={messages}
                onSendMessage={handleSendMessage}
                loading={chatting}
                agentName={selectedAgent.name}
              />
            </div>

            <div>
              <h2 className="text-xl font-bold mb-4">Generated Files</h2>
              <FileExplorer files={files} onDownload={handleDownload} downloading={downloading} />
            </div>
          </section>
        )}
      </main>

      <footer className="border-t mt-12 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>GitAgent-Clon - Clone, detect and execute AI agents from Git repositories</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
