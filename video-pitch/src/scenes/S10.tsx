import { AbsoluteFill } from "remotion";
import { C, Chip, FadeUp, H, SceneFade, Stage, cue, vo } from "../kit";

// What we learned: honest limit and next step.
export const S10: React.FC<{ dur: number }> = ({ dur }) => (
  <SceneFade dur={dur}>
    <Stage glow={0.3}>
      <AbsoluteFill style={{ justifyContent: "center", paddingLeft: 220 }}>
        <FadeUp at={vo(0)}><H size={84} color={C.sub}>The hard part was not the brain.</H></FadeUp>
        <FadeUp at={cue("s10", "fingers", 0, vo(2.6))}><H size={96} style={{ marginTop: 20 }}>It was the fingers.</H></FadeUp>
        <FadeUp at={cue("s10", "millimetres", 0, vo(4.5))}><div style={{ marginTop: 50 }}><Chip size={36} color={C.red} fill>a few mm of camera error → a round object slips</Chip></div></FadeUp>
        <FadeUp at={cue("s10", "next", 0, vo(8))}><div style={{ marginTop: 24 }}><Chip size={36}>next: re-check with the wrist camera before closing</Chip></div></FadeUp>
      </AbsoluteFill>
    </Stage>
  </SceneFade>
);
