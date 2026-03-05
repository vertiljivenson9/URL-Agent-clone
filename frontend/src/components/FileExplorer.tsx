import { useState } from 'react';
import { FileCode, Folder, Download, X } from 'lucide-react';
import { Button } from './ui/Button';
import { cn } from '@/utils/cn';
import type { FileInfo } from '@/types';
import Prism from 'prismjs';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-json';

interface FileExplorerProps {
  files: FileInfo[];
  onDownload: () => void;
  downloading: boolean;
}

function getLang(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = { js: 'javascript', ts: 'typescript', py: 'python', json: 'json' };
  return map[ext] || 'text';
}

export function FileExplorer({ files, onDownload, downloading }: FileExplorerProps) {
  const [activeFile, setActiveFile] = useState<string | null>(files[0]?.path || null);
  const [openTabs, setOpenTabs] = useState<string[]>(files[0] ? [files[0].path] : []);

  const activeFileData = files.find(f => f.path === activeFile);

  const handleFileClick = (file: FileInfo) => {
    if (!openTabs.includes(file.path)) setOpenTabs([...openTabs, file.path]);
    setActiveFile(file.path);
  };

  const handleCloseTab = (path: string) => {
    const newTabs = openTabs.filter(p => p !== path);
    setOpenTabs(newTabs);
    if (activeFile === path) setActiveFile(newTabs[newTabs.length - 1] || null);
  };

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-muted-foreground">
        <Folder className="h-12 w-12 mb-4 opacity-50" />
        <p>No files generated yet</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border rounded-lg bg-card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <Folder className="h-5 w-5 text-primary" />
          <span className="font-medium">Generated Files</span>
          <span className="text-xs text-muted-foreground">({files.length})</span>
        </div>
        <Button variant="outline" size="sm" onClick={onDownload} disabled={downloading}>
          <Download className="h-4 w-4 mr-2" />
          Download ZIP
        </Button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-48 border-r bg-muted/50 overflow-auto">
          <div className="p-2">
            <p className="text-xs font-medium text-muted-foreground px-2 py-1">EXPLORER</p>
            {files.map((file) => (
              <button
                key={file.path}
                onClick={() => handleFileClick(file)}
                className={cn("w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-accent", activeFile === file.path && "bg-accent")}
              >
                <FileCode className="h-4 w-4 text-muted-foreground" />
                <span className="truncate">{file.name}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          {openTabs.length > 0 && (
            <div className="flex border-b bg-muted/50 overflow-x-auto">
              {openTabs.map((path) => {
                const file = files.find(f => f.path === path);
                if (!file) return null;
                return (
                  <button
                    key={path}
                    onClick={() => setActiveFile(path)}
                    className={cn("flex items-center gap-2 px-3 py-2 text-xs border-r hover:bg-background", activeFile === path && "bg-background")}
                  >
                    <FileCode className="h-3 w-3" />
                    {file.name}
                    <X className="h-3 w-3 hover:text-destructive" onClick={(e) => { e.stopPropagation(); handleCloseTab(path); }} />
                  </button>
                );
              })}
            </div>
          )}

          {activeFileData && (
            <div className="flex-1 overflow-auto p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">{activeFileData.path}</span>
                <span className="text-xs text-muted-foreground">{activeFileData.size} bytes</span>
              </div>
              <pre className="rounded-md bg-muted p-4 overflow-x-auto text-sm font-mono">
                <code dangerouslySetInnerHTML={{ __html: Prism.highlight(activeFileData.content, Prism.languages[getLang(activeFileData.name)] || Prism.languages.text, getLang(activeFileData.name)) }} />
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
