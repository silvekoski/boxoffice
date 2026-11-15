import { AbsoluteFill, Img, staticFile } from "remotion";
import { C, Chip, FadeUp, Label, Panel, SceneFade, Stage, cue, vo } from "../kit";

// The task on the sim's own head-camera frame, and the scoring.
export const S03: React.FC<{ dur: number }> = ({ dur }) => (
  <SceneFade dur={dur}>
    <Stage glow={0.3}>
      <AbsoluteFill style={{ padding: "120px 120px", flexDirection: "row", gap: 70, alignItems: "center" }}>
        <FadeUp at={vo(0)}>
          <Panel style={{ padding: 10 }}><Img src={staticFile("img/sim_head.jpg")} style={{ width: 960, display: "block", borderRadius: 8 }} /></Panel>
          <Label size={24} color={C.dim} style={{ marginTop: 14 }}>Aalto’s simulator · head camera · our policy running</Label>
        </FadeUp>
        <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
          <FadeUp at={cue("s03", "Three", 0, vo(0.3))}><Chip size={40}>3–5 objects</Chip></FadeUp>
          <FadeUp at={cue("s03", "boxes", 0, vo(2.6))}><Chip size={40}>3 boxes · 2 minutes</Chip></FadeUp>
          <FadeUp at={cue("s03", "right", 0, vo(4.5))}><Chip size={40} color={C.good} fill>+ right box</Chip></FadeUp>
          <FadeUp at={cue("s03", "wrong", 0, vo(5.8))}><Chip size={40} color={C.red} fill>− wrong box</Chip></FadeUp>
          <FadeUp at={cue("s03", "skips", 0, vo(8))}><Chip size={40}>unsure → skip (0)</Chip></FadeUp>
        </div>
      </AbsoluteFill>
    </Stage>
  </SceneFade>
);
