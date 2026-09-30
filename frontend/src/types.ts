export type Source = { id: string; guest: string; episode: string; timestamp: string; url: string; score: number; excerpt: string; label: string };
export type Artifact = { id: string; artifact_type: 'markdown' | 'html'; title: string; content: string };
export type Message = { id: string; role: string; content: string; sources: Source[]; artifact?: Artifact | null };
export type Session = { id: string; title: string };
export type Health = { status: string; chunks: number; episodes: number; database: boolean; vector_index: boolean; ollama: boolean; embedding_model: boolean; chat_model: boolean; providers: { ollama: boolean; anthropic: boolean } };
