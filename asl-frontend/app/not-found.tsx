import Link from "next/link";

export default function NotFound() {
  return (
    <>
      <h1>Not found</h1>
      <p className="dim">
        That page or score doesn&apos;t exist &mdash; the link may be wrong or
        the analysis may have been removed.
      </p>
      <p>
        <Link href="/">Back to ASL</Link> &middot;{" "}
        <Link href="/leaderboard">Leaderboard</Link>
      </p>
    </>
  );
}
