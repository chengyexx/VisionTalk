declare module "@ricky0123/vad-web" {
  export interface MicVADOptions {
    onSpeechStart?: () => void;
    onSpeechEnd?: () => void;
    onVADMisfire?: () => void;
    model?: "v5" | "legacy";
    baseAssetPath?: string;
    ortConfig?: (ort: { env: { wasm: { wasmPaths: string } } }) => void;
  }

  export class MicVAD {
    static new(options: MicVADOptions): Promise<MicVAD>;
    start(): void;
    destroy(): void;
  }
}
