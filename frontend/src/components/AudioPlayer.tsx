import { useRef, useEffect } from "react";
import { motion } from "motion/react";

interface AudioPlayerProps {
  audioUrl?: string;
  isPlaying: boolean;
  onEnded?: () => void;
}

export function AudioPlayer({ audioUrl, isPlaying, onEnded }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    const el = audioRef.current;
    if (!el || !audioUrl) return;

    if (isPlaying) {
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [isPlaying, audioUrl]);

  return (
    <motion.div
      className={`audio-player ${isPlaying ? "playing" : ""}`}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{
        opacity: isPlaying ? 1 : 0,
        scale: isPlaying ? 1 : 0.9,
      }}
      transition={{ duration: 0.25 }}
    >
      {isPlaying && (
        <>
          <div className="audio-bars">
            {[0, 1, 2, 3, 4].map((i) => (
              <motion.div
                key={i}
                className="audio-bar"
                animate={{ height: [8, 24, 12, 28, 16][i] }}
                transition={{ repeat: Infinity, duration: 0.6, delay: i * 0.1, repeatType: "reverse" }}
              />
            ))}
          </div>
          <span className="audio-label">AI 正在说话</span>
        </>
      )}
      <audio ref={audioRef} src={audioUrl} onEnded={onEnded} />
    </motion.div>
  );
}
