import { Bot, Check } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/Card';
import { Badge } from './ui/Badge';
import { cn } from '@/utils/cn';
import type { Agent } from '@/types';

interface AgentGridProps {
  agents: Agent[];
  selectedAgent: Agent | null;
  onSelectAgent: (agent: Agent) => void;
}

export function AgentGrid({ agents, selectedAgent, onSelectAgent }: AgentGridProps) {
  if (agents.length === 0) {
    return (
      <div className="text-center py-12">
        <Bot className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold">No agents detected</h3>
        <p className="text-muted-foreground">No agent files found in this repository.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {agents.map((agent) => {
        const isSelected = selectedAgent?.id === agent.id;
        return (
          <Card
            key={agent.id}
            className={cn("cursor-pointer transition-all hover:shadow-md", isSelected && "ring-2 ring-primary")}
            onClick={() => onSelectAgent(agent)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{agent.icon}</span>
                  <div>
                    <CardTitle className="text-lg">{agent.name}</CardTitle>
                    <Badge variant="secondary" className="mt-1">{agent.type}</Badge>
                  </div>
                </div>
                {isSelected && (
                  <div className="h-6 w-6 rounded-full bg-primary flex items-center justify-center">
                    <Check className="h-4 w-4 text-primary-foreground" />
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription className="line-clamp-3">{agent.description}</CardDescription>
              <p className="text-xs text-muted-foreground mt-2 truncate">{agent.path}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
