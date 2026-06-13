import { useRef, forwardRef, useImperativeHandle } from "react";
import Webcam from "react-webcam";

export interface CameraHandle {
  captureFrame: () => string | null;
}

interface CameraProps {
  width?: number;
  height?: number;
  mirrored?: boolean;
  className?: string;
}

const Camera = forwardRef<CameraHandle, CameraProps>(
  ({ width = 640, height = 480, mirrored = true, className }, ref) => {
    const webcamRef = useRef<Webcam>(null);

    useImperativeHandle(ref, () => ({
      captureFrame: (): string | null => {
        const screenshot = webcamRef.current?.getScreenshot();
        return screenshot ?? null;
      },
    }));

    return (
      <div className={className}>
        <Webcam
          ref={webcamRef}
          audio={false}
          width={width}
          height={height}
          mirrored={mirrored}
          screenshotFormat="image/jpeg"
          screenshotQuality={0.85}
          videoConstraints={{
            width,
            height,
            facingMode: "user",
          }}
          style={{ borderRadius: "8px", width: "100%", maxWidth: width }}
        />
      </div>
    );
  }
);

Camera.displayName = "Camera";

export default Camera;
