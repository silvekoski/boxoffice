import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { C, MONO, SceneFade, Stage, TEXT, prog } from "../kit";

// End card: logo, line, team.
export const S08: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const t = prog(f, 0, 24);
  return (
    <SceneFade dur={dur} outF={20}>
      <Stage glow={0.9} glowY={50}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", opacity: t }}>
          <Img src={staticFile("img/rebus.png")} style={{ width: 900, marginTop: -160, marginBottom: -110 }} />
          <div style={{ fontFamily: TEXT, fontSize: 110, fontWeight: 700, color: C.text, letterSpacing: "-0.03em" }}>Box Office</div>
          <div style={{ fontFamily: TEXT, fontSize: 52, fontWeight: 600, color: C.text, marginTop: 10 }}>Plain words in. Sorted boxes out.</div>
          <div style={{ fontFamily: MONO, fontSize: 26, color: C.sub, marginTop: 30 }}>Team Bob the builders · Junction 2026 · Aaltonomous Humanoid</div>
        </AbsoluteFill>
      </Stage>
    </SceneFade>
  );
};
