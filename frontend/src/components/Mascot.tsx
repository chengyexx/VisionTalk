import { useEffect, useState, useRef } from "react";
import lottie, { type AnimationItem } from "lottie-web";
import mascotAnim from "../assets/mascot-settings.json";
import "./Mascot.css";

export type MascotState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "startled";

interface MascotProps {
  state: MascotState;
}

const BUBBLES: Record<MascotState, string> = {
  idle: "",
  listening: "在听呢~",
  thinking: "嗯...",
  speaking: "",
  startled: "！",
};

/** Lottie 播放片段 [startFrame, endFrame] */
const SEGMENTS: Record<MascotState, [number, number]> = {
  idle: [0, 60],
  listening: [0, 60],
  thinking: [60, 123],
  speaking: [123, 211],
  startled: [180, 211],
};

export default function Mascot({ state }: MascotProps) {
  const [bubble, setBubble] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const animRef = useRef<AnimationItem | null>(null);

  // ── 初始化 Lottie ──
  useEffect(() => {
    if (!containerRef.current) return;
    const anim = lottie.loadAnimation({
      container: containerRef.current,
      renderer: "svg",
      loop: true,
      autoplay: true,
      animationData: mascotAnim,
      rendererSettings: {
        preserveAspectRatio: "xMidYMid meet",
      },
    });
    animRef.current = anim;
    return () => anim.destroy();
  }, []);

  // ── 状态切换 → 播放对应片段 ──
  useEffect(() => {
    const anim = animRef.current;
    if (!anim) return;
    const [start, end] = SEGMENTS[state];
    anim.playSegments([start, end], true);
    anim.loop = state === "speaking" || state === "idle" || state === "listening";
  }, [state]);

  // ── 气泡文字 ──
  useEffect(() => {
    if (state === "startled") {
      setBubble("！");
      const t = setTimeout(() => setBubble(""), 1200);
      return () => clearTimeout(t);
    }
    setBubble(state === "speaking" || state === "idle" ? "" : BUBBLES[state]);
  }, [state]);

  return (
    <div className={`mascot-wrap mascot-${state}`}>
      {bubble && <div className="mascot-bubble">{bubble}</div>}

      <div
        ref={containerRef}
        className="mascot-lottie"
        style={{ width: 180, height: 180 }}
      />

      <div className="mascot-credit">
        <a href="https://iconscout.com/lottie-animations/settings" target="_blank" rel="noopener">
          Settings
        </a>
        {" by "}
        <a href="https://iconscout.com/contributors/meetanshi" target="_blank" rel="noopener">
          Meetanshi Technologies
        </a>
        {" on "}
        <a href="https://iconscout.com" target="_blank" rel="noopener">
          IconScout
        </a>
      </div>
    </div>
  );
}
