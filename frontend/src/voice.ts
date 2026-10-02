import type { Conversation } from '@elevenlabs/client';
import type { Connection } from './types';

export type VoiceEvents = {
  message: (speaker: 'learner' | 'tutor', text: string) => void;
  status: (status: string) => void;
  disconnected: () => void;
  error: () => void;
};

export class Voice {
  private conversation: Conversation | null = null;
  private ended = false;

  async start(connection: Connection, events: VoiceEvents): Promise<string> {
    this.ended = false;
    if (connection.mode === 'fake') {
      events.status('Simulation active');
      events.message('tutor', 'What did you do yesterday?');
      events.message('learner', 'Yesterday I go to the market.');
      if (!connection.conversation_id) throw new Error('Missing simulation conversation ID.');
      return connection.conversation_id;
    }
    if (!connection.signed_url) throw new Error('Missing ElevenLabs connection descriptor.');
    try {
      const { Conversation } = await import('@elevenlabs/client');
      if (this.ended) throw new Error('Connection cancelled.');
      const conversation = await Conversation.startSession({
        signedUrl: connection.signed_url,
        connectionType: 'websocket',
        dynamicVariables: connection.dynamic_variables,
        onConversationCreated: current => {
          this.conversation = current;
          if (this.ended) void current.endSession().catch(() => {});
        },
        onMessage: message => {
          if (!this.ended) events.message(message.source === 'user' ? 'learner' : 'tutor', message.message);
        },
        onModeChange: mode => {
          if (!this.ended) events.status(mode.mode === 'speaking' ? 'Tutor speaking' : 'Listening');
        },
        onStatusChange: status => { if (!this.ended) events.status(status.status); },
        onDisconnect: () => { if (!this.ended) events.disconnected(); },
        onError: () => { if (!this.ended) events.error(); },
      });
      if (this.ended) {
        await conversation.endSession();
        throw new Error('Connection cancelled.');
      }
      this.conversation = conversation;
      return conversation.getId();
    } catch {
      // SDK error payloads can include provider details; show only our own message.
      throw new Error('Voice connection failed. Check microphone permission and ElevenLabs agent access.');
    }
  }

  mute(muted: boolean) { this.conversation?.setMicMuted(muted); }

  async end() {
    this.ended = true;
    const current = this.conversation;
    this.conversation = null;
    try { if (current) await current.endSession(); }
    catch { throw new Error('Voice cleanup failed. Close this browser tab to release the microphone.'); }
  }
}
