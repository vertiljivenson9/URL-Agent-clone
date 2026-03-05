export interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  path: string;
  full_path: string;
  type: string;
}

export interface FileInfo {
  name: string;
  path: string;
  content: string;
  size: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  files?: string[];
  error?: string;
}
