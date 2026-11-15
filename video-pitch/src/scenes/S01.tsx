import { AbsoluteFill } from "remotion";
import { C, FadeUp, H, Label, MONO, SceneFade, Stage, cue, vo } from "../kit";

// Hook: one real robot, one real problem.
export const S01: React.FC<{ dur: number }> = ({ dur }) => (
  <SceneFade dur={dur}>
    <Stage glow={0.4}>
      <AbsoluteFill style={{ justifyContent: "center", paddingLeft: 220 }}>
        <FadeUp at={vo(0)}><Label style={{ fontFamily: MONO }} size={28} color={C.dim}>Unitree G1 · “Väiski” · Aalto University</Label></FadeUp>
        <FadeUp at={cue("s01", "backflip", 0, vo(2.5))}><H size={96} style={{ marginTop: 24 }}>Backflips: easy.</H></FadeUp>
        <FadeUp at={cue("s01", "Ask", 0, vo(4))}><H size={96} color={C.sub}>Three blocks, three boxes:</H></FadeUp>
        <FadeUp at={cue("s01", "lost", 0, vo(6.5))}><H size={96} color={C.red} style={{ marginTop: 24 }}>lost.</H></FadeUp>
      </AbsoluteFill>
    </Stage>
  </SceneFade>
);
