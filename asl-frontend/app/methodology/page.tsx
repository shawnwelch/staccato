import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How ASL measures shot pacing: shot detection, median shot length, a logistic 0-100 scale, and versioned scoring.",
};

export default function MethodologyPage() {
  return (
    <>
      <h1>Methodology</h1>
      <p className="lede">
        ASL is an instrument. It measures one thing &mdash; how fast a video
        changes shots &mdash; and reports it on a fixed, versioned scale.
      </p>

      <h2>What the score measures</h2>
      <p>
        The engine detects shot boundaries (cuts) in a video, computes the{" "}
        <strong>median shot length</strong>, and maps it onto a 0&ndash;100
        pacing intensity score with a logistic curve. The curve&apos;s midpoint
        is calibrated so that a median shot length of{" "}
        <span className="mono">11 seconds</span> scores{" "}
        <span className="mono">50</span>. Shorter median shots push the score
        toward 100; longer ones toward 0.
      </p>

      <h2>Labels</h2>
      <p>
        Labels are descriptive bands on the same scale &mdash; they describe
        the measurement, nothing else:
      </p>
      <div className="tableWrap" style={{ maxWidth: "28rem" }}>
        <table>
          <thead>
            <tr>
              <th>Score</th>
              <th>Label</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="num">0 &ndash; 24</td>
              <td>calm</td>
            </tr>
            <tr>
              <td className="num">25 &ndash; 49</td>
              <td>moderate</td>
            </tr>
            <tr>
              <td className="num">50 &ndash; 74</td>
              <td>fast</td>
            </tr>
            <tr>
              <td className="num">75 &ndash; 100</td>
              <td>hyper-paced</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2>Versioned scoring</h2>
      <p>
        Every score carries the <span className="mono">engine_version</span>{" "}
        that produced it. When the engine changes, the version number changes
        &mdash; existing scores are <strong>never silently rescored</strong>.
        A score you shared yesterday means the same thing tomorrow.
      </p>

      <h2>Open source</h2>
      <p>
        The scoring engine will be open-sourced, so anyone can inspect exactly
        how a number was produced and reproduce it independently.
      </p>
    </>
  );
}
