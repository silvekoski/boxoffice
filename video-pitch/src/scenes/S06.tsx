import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, Chip, FadeUp, H, Label, MONO, SceneFade, Stage, TEXT, cue, prog, vo } from "../kit";

// Results on randomised sim scenes, same seeds (results/sim-dr-v9-2026-11-15/README.md).
const GROUPS = [
  { name: "fixed sorting", word: "ten", nth: 0, vals: [[8, 20], [10, 20]] },
  { name: "by instruction", word: "eighteen", nth: 0, vals: [[12, 18], [10, 18]] },
];
export const S06: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  return (
    <SceneFade dur={dur}>
      <Stage glow={0.4}>
        <AbsoluteFill style={{ padding: "130px 120px" }}>
          <FadeUp at={vo(0)}><H size={66}>Aalto’s simulator, randomised scenes</H></FadeUp>
          <FadeUp at={vo(0.4)}><Label size={26} color={C.dim} style={{ marginTop: 12 }}>■ first version   <span style={{ color: C.good }}>■ Box Office</span>   · objects in the right box, same 10 scenes</Label></FadeUp>
          <div style={{ position: "absolute", left: 160, top: 360, width: 1000, height: 460 }}>
            {GROUPS.map((g, gi) => {
              const t0 = cue("s06", g.word, g.nth, vo(4 + gi * 3));
              return g.vals.map((v, i) => {
                const t = prog(f, t0 + i * 10, 20);
                const h = (v[0] / v[1]) * 380 * t;
                const x = gi * 470 + i * 180;
                return (
                  <div key={g.name + i}>
                    <div style={{ position: "absolute", left: x, top: 420 - h, width: 150, height: h, background: i ? C.good : "#5A6475", borderRadius: "10px 10px 0 0" }} />
                    <div style={{ position: "absolute", left: x, top: 420 - h - 58, width: 150, textAlign: "center", fontFamily: MONO, fontSize: 40, fontWeight: 600, color: i ? C.good : C.sub, opacity: t }}>{v[0]}/{v[1]}</div>
                    {i === 0 && <div style={{ position: "absolute", left: x, top: 440, width: 330, textAlign: "center", fontFamily: TEXT, fontSize: 30, color: C.sub, opacity: prog(f, t0, 12) }}>{g.name}</div>}
                  </div>
                );
              });
            })}
          </div>
          <div style={{ position: "absolute", left: 1220, top: 400, display: "flex", flexDirection: "column", gap: 26 }}>
            <FadeUp at={cue("s06", "Not", 0, vo(9))}><Chip size={38} color={C.good} fill>0 wrong boxes</Chip></FadeUp>
            <FadeUp at={cue("s06", "never", 0, vo(11))}><Chip size={38} color={C.good} fill>0 safety clips</Chip></FadeUp>
          </div>
        </AbsoluteFill>
      </Stage>
    </SceneFade>
  );
};
