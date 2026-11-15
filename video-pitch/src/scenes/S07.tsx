import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, FadeUp, H, Label, MONO, SceneFade, Stage, cue, prog, vo } from "../kit";

// Real-robot timing: first move after 1 s instead of up to 52 s (commit 0461a215, real frames).
export const S07: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const t1 = cue("s07", "one", 0, vo(3));
  const old = prog(f, cue("s07", "fifty-two", 0, vo(4)), 14);
  return (
    <SceneFade dur={dur}>
      <Stage glow={0.6}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
          <FadeUp at={vo(0)}><Label size={30} color={C.dim}>time until the robot starts moving · real venue frames</Label></FadeUp>
          <div style={{ display: "flex", gap: 120, marginTop: 40, alignItems: "baseline" }}>
            <div style={{ opacity: old, fontFamily: MONO, fontSize: 150, color: C.dim, textDecoration: "line-through" }}>52 s</div>
            <FadeUp at={t1}><div style={{ fontFamily: MONO, fontSize: 220, fontWeight: 700, color: C.good }}>1 s</div></FadeUp>
          </div>
          <FadeUp at={t1 + 20}><H size={40} color={C.sub} style={{ marginTop: 20 }}>the slow, failing plans now come last</H></FadeUp>
        </AbsoluteFill>
      </Stage>
    </SceneFade>
  );
};
