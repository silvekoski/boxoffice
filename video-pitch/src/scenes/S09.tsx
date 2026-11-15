import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, FadeUp, H, Panel, SceneFade, Stage, TEXT, cue, prog, vo } from "../kit";

// How it works: four stages, each lights up on its word.
const STEPS = [
  { word: "camera", title: "Head camera", sub: "colour + depth → objects and shapes" },
  { word: "parser", title: "Parser", sub: "sentence → a box per object" },
  { word: "planner", title: "Aalto’s planner", sub: "grasp, carry, release" },
  { word: "safety", title: "Safety filter", sub: "every move checked first" },
];
export const S09: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  return (
    <SceneFade dur={dur}>
      <Stage glow={0.4}>
        <AbsoluteFill style={{ padding: "150px 120px" }}>
          <FadeUp at={vo(0)}><H size={72}>Under the hood</H></FadeUp>
          <div style={{ display: "flex", gap: 30, marginTop: 90 }}>
            {STEPS.map((s, i) => {
              const t = prog(f, cue("s09", s.word, 0, vo(1 + i * 2.6)), 16);
              const last = i === STEPS.length - 1;
              return (
                <Panel key={s.word} style={{ width: 400, height: 300, padding: 34, opacity: 0.25 + 0.75 * t, borderColor: last && t > 0.5 ? C.good : C.line, transform: `translateY(${(1 - t) * 12}px)` }}>
                  <div style={{ fontFamily: TEXT, fontSize: 26, color: C.dim }}>{String(i + 1).padStart(2, "0")}</div>
                  <div style={{ fontFamily: TEXT, fontSize: 44, fontWeight: 600, color: C.text, marginTop: 20 }}>{s.title}</div>
                  <div style={{ fontFamily: TEXT, fontSize: 30, color: C.sub, marginTop: 18 }}>{s.sub}</div>
                </Panel>
              );
            })}
          </div>
        </AbsoluteFill>
      </Stage>
    </SceneFade>
  );
};
