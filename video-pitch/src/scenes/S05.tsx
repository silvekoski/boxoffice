import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { C, Chip, FadeUp, Label, Panel, SceneFade, Stage, cue, prog, vo } from "../kit";

// Real venue frame (Aalto, Drop 3): stock colour rules, then Box Office; then the 14° camera tilt.
export const S05: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const after = prog(f, cue("s05", "finds", 0, vo(7)), 18);
  return (
    <SceneFade dur={dur}>
      <Stage glow={0.3}>
        <AbsoluteFill style={{ padding: "120px 120px", flexDirection: "row", gap: 70, alignItems: "center" }}>
          <FadeUp at={vo(0)}>
            <Panel style={{ padding: 10, position: "relative" }}>
              <div style={{ position: "relative", width: 960, height: 720 }}>
                <Img src={staticFile("img/real_before.jpg")} style={{ position: "absolute", width: 960, borderRadius: 8 }} />
                <Img src={staticFile("img/real_after.jpg")} style={{ position: "absolute", width: 960, borderRadius: 8, opacity: after }} />
              </div>
            </Panel>
            <Label size={24} color={C.dim} style={{ marginTop: 14 }}>real venue recording · Aalto University, Hugging Face (Apache-2.0)</Label>
          </FadeUp>
          <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
            <FadeUp at={cue("s05", "boxes", 0, vo(4))}><Chip size={36} color={C.red} fill>boxes seen as objects</Chip></FadeUp>
            <FadeUp at={cue("s05", "hands", 0, vo(5))}><Chip size={36} color={C.red} fill>hands seen as objects</Chip></FadeUp>
            <FadeUp at={cue("s05", "finds", 0, vo(7))}><Chip size={36} color={C.good} fill>132 → 74 detections</Chip></FadeUp>
            <FadeUp at={cue("s05", "tilted", 0, vo(10))}><Chip size={36} color={C.good} fill>14° camera tilt levelled</Chip></FadeUp>
          </div>
        </AbsoluteFill>
      </Stage>
    </SceneFade>
  );
};
