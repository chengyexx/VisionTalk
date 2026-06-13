import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";

interface Model {
  id: string;
  label: string;
  description: string;
}

const AVAILABLE_MODELS: Model[] = [
  { id: "deepseek/deepseek-chat", label: "DeepSeek-V3", description: "默认推荐，性价比最高" },
  { id: "deepseek/deepseek-reasoner", label: "DeepSeek-R1", description: "深度推理，复杂问题" },
  { id: "gpt-4o", label: "GPT-4o", description: "OpenAI 多模态旗舰" },
  { id: "qwen/qwen-vl-max", label: "Qwen-VL-Max", description: "通义千问视觉模型" },
];

interface ModelSelectorProps {
  currentModel: string;
  onChange?: (modelId: string) => void;
}

export function ModelSelector({ currentModel, onChange }: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const current = AVAILABLE_MODELS.find((m) => m.id === currentModel) || AVAILABLE_MODELS[0];

  const handleSelect = useCallback(
    (model: Model) => {
      setOpen(false);
      onChange?.(model.id);
    },
    [onChange]
  );

  return (
    <div className="model-selector">
      <button
        className="model-trigger"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="model-label">{current.label}</span>
        <motion.span
          className="model-chevron"
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          ▾
        </motion.span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="model-dropdown"
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ duration: 0.18 }}
          >
            {AVAILABLE_MODELS.map((model) => (
              <button
                key={model.id}
                className={`model-option ${model.id === currentModel ? "active" : ""}`}
                onClick={() => handleSelect(model)}
              >
                <div className="model-option-label">{model.label}</div>
                <div className="model-option-desc">{model.description}</div>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
