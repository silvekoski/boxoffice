import { AbsoluteFill } from "remotion";
import { C, Chip, FadeUp, H, SceneFade, Stage, Type, cue, vo } from "../kit";

// Language: two unseen phrasings typed, then the box each gives.
export const S04: React.FC<{ dur: number }> = ({ dur }) => (
  <SceneFade dur={dur}>
    <Stage glow={0.4}>
      <AbsoluteFill style={{ padding: "150px 160px", gap: 60 }}>
        <FadeUp at={vo(0)}><H size={72}>Say it in your own words</H></FadeUp>
        <div style={{ display: "flex", alignItems: "center", gap: 40, fontSize: 48, color: C.text }}>
          <div style={{ width: 900 }}>“<Type text="the blue ones in between" at={cue("s04", "blue", 0, vo(3.5))} cps={30} />”</div>
          <FadeUp at={cue("s04", "between", 0, vo(4.5)) + 10}><Chip size={44} color={C.good} fill>blue → centre</Chip></FadeUp>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 40, fontSize: 48, color: C.text }}>
          <div style={{ width: 900 }}>“<Type text="the first box from the left" at={cue("s04", "first", 0, vo(5.5))} cps={30} />”</div>
          <FadeUp at={cue("s04", "left", 0, vo(6.8)) + 10}><Chip size={44} color={C.good} fill>→ left box</Chip></FadeUp>
        </div>
        <FadeUp at={cue("s04", "templates", 0, vo(8))}><Chip size={36}>no templates · 26 unseen phrasings in the tests</Chip></FadeUp>
      </AbsoluteFill>
    </Stage>
  </SceneFade>
);
