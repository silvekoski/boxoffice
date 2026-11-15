import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { C, MONO, SceneFade, Stage, TEXT, prog } from "../kit";

// Opening card: the rebus logo, then the challenge line. No voice.
export const S00: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const t = prog(f, 4, 30);
  const sub = prog(f, 22, 24);
  return (
    <SceneFade dur={dur} inF={1} outF={12}>
      <Stage glow={0.9} glowY={40}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div style={{ opacity: t, transform: `scale(${0.96 + 0.04 * t})`, filter: `blur(${(1 - t) * 8}px)` }}>
            <div style={{ textAlign: "center", fontFamily: TEXT, fontSize: 96, fontWeight: 700, color: C.text, letterSpacing: "-0.03em", marginBottom: 10 }}>‘Box - Off - Ice’</div>
            <Img src={staticFile("img/rebus.png")} style={{ width: 1100, marginTop: -220 }} />
          </div>
          <div style={{ marginTop: 10, opacity: sub, fontFamily: MONO, fontSize: 26, color: C.sub, letterSpacing: "0.04em" }}>JUNCTION 2026 · AALTONOMOUS HUMANOID</div>
        </AbsoluteFill>
      </Stage>
    </SceneFade>
  );
};
