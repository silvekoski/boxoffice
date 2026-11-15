import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { C, H, MONO, SceneFade, Stage, cue, prog, vo } from "../kit";

// The name as a rebus: Box · Off · Ice, revealed piece by piece on the spoken words (crops of the logo poster).
const PIECES = [
  { word: "Box", x: 30, w: 430 },
  { word: "Off", x: 470, w: 300 },
  { word: "Ice", x: 790, w: 380 },
];
export const S02: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const name = prog(f, cue("s02", "Office", 0, vo(3.6)), 18);
  const brain = prog(f, vo(0), 14) * (1 - prog(f, cue("s02", "Box", 0, vo(1.6)) - 8, 10));
  return (
    <SceneFade dur={dur}>
      <Stage glow={0.6}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: brain }}>
          <H size={96}>So we gave it a brain.</H>
        </AbsoluteFill>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div style={{ position: "relative", width: 1200, height: 520 }}>
            {PIECES.map((p, i) => {
              const t = prog(f, cue("s02", p.word, 0, vo(1.6 + i * 0.6)), 14);
              return (
                <div key={p.word} style={{ position: "absolute", left: p.x, top: 0, width: p.w, height: 520, overflow: "hidden", opacity: t, transform: `translateY(${(1 - t) * 20}px)` }}>
                  <Img src={staticFile("img/rebus.png")} style={{ position: "absolute", left: -p.x, top: -250, width: 1200 }} />
                  <div style={{ position: "absolute", bottom: 0, width: "100%", textAlign: "center", fontFamily: MONO, fontSize: 30, color: C.accent }}>{p.word.toUpperCase()}</div>
                </div>
              );
            })}
          </div>
          <div style={{ opacity: name, marginTop: 30 }}><H size={120} weight={700}>Box Office</H></div>
        </AbsoluteFill>
      </Stage>
    </SceneFade>
  );
};
